import re
from datetime import timedelta
from functools import cached_property
from typing import TYPE_CHECKING

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import connection, models
from django.db.models import Avg, Count, F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from catalog.collection.models import Collection as CatalogCollection
from catalog.models import Item
from users.models import APIdentity

from .itemlist import List, ListMember


class TagMember(ListMember):
    if TYPE_CHECKING:
        parent: models.ForeignKey["TagMember", "Tag"]
    parent = models.ForeignKey("Tag", related_name="members", on_delete=models.CASCADE)

    class Meta:
        unique_together = [["parent", "item"]]

    @property
    def ap_object(self):
        return {
            "id": self.absolute_url,
            "type": "Tag",
            "tag": self.parent.title,
            "published": self.created_time.isoformat(),
            "updated": self.edited_time.isoformat(),
            "attributedTo": self.owner.actor_uri,
            "withRegardTo": self.item.absolute_url,
            "href": self.absolute_url,
        }


TagValidators = [RegexValidator(regex=r"\s+", inverse_match=True)]


class Tag(List):
    MEMBER_CLASS = TagMember
    items = models.ManyToManyField(Item, through="TagMember")
    title = models.CharField(
        max_length=100, null=False, blank=False, validators=TagValidators
    )
    pinned = models.BooleanField(default=False, null=True)

    class Meta:
        unique_together = [["owner", "title"]]

    @staticmethod
    def cleanup_title(title, replace=True):
        t = re.sub(r"\s+", " ", title.rstrip().lstrip("# "))
        return "_" if not t and replace else t

    @staticmethod
    def deep_cleanup_title(title):
        """Remove all non-word characters, only for public index purpose"""
        return re.sub(r"\W+", " ", title).rstrip().lstrip("# ").lower()[:100] or "_"

    def update(
        self, title: str, visibility: int | None = None, pinned: bool | None = None
    ):
        old_title = Tag.deep_cleanup_title(self.title)
        new_title = Tag.deep_cleanup_title(title)
        was_pinned = bool(self.pinned)
        if visibility is not None:
            self.visibility = 2 if visibility else 0
        if pinned is not None:
            self.pinned = pinned
        self.title = title
        self.save()
        if was_pinned != self.pinned or (old_title != new_title and self.pinned):
            from takahe.utils import Takahe

            if was_pinned:
                Takahe.unpin_hashtag_for_user(self.owner.pk, old_title)
            if self.pinned:
                Takahe.pin_hashtag_for_user(self.owner.pk, new_title)


class TagManager:
    @staticmethod
    def indexable_tags_for_item(item):
        tags = (
            item.tag_set.all()
            .filter(visibility=0)
            .values("title")
            .annotate(frequency=Count("owner"))
            .order_by("-frequency")[:20]
        )
        tag_titles = sorted(
            [
                t
                for t in set(map(lambda t: Tag.deep_cleanup_title(t["title"]), tags))
                if t and t != "_"
            ]
        )
        return tag_titles

    @staticmethod
    def all_tags_by_owner(owner, public_only=False):
        tags = owner.tag_set.all().annotate(total=Count("members")).order_by("-total")
        if public_only:
            tags = tags.filter(visibility=0)
        return tags

    @staticmethod
    def tag_item_for_owner(
        owner: APIdentity,
        item: Item,
        tag_titles: list[str],
        default_visibility: int = 0,
    ):
        titles = set([Tag.cleanup_title(tag_title) for tag_title in tag_titles])
        current_titles = set(
            [m.parent.title for m in TagMember.objects.filter(owner=owner, item=item)]
        )
        for title in titles - current_titles:
            tag = Tag.objects.filter(owner=owner, title=title).first()
            if not tag:
                tag = Tag.objects.create(
                    owner=owner, title=title, visibility=default_visibility
                )
            tag.append_item(item, visibility=default_visibility)
        for title in current_titles - titles:
            tag = Tag.objects.filter(owner=owner, title=title).first()
            if tag:
                tag.remove_item(item)

    def tag_item(self, item: Item, tag_titles: list[str], default_visibility: int = 0):
        TagManager.tag_item_for_owner(self.owner, item, tag_titles, default_visibility)

    @staticmethod
    def get_manager_for_user(owner):
        return TagManager(owner)

    def __init__(self, owner):
        self.owner = owner

    @property
    def all_tags(self):
        return TagManager.all_tags_by_owner(self.owner)

    @property
    def public_tags(self):
        return TagManager.all_tags_by_owner(self.owner, public_only=True)

    @staticmethod
    def popular_tags(days: int = 30):
        t = timezone.now() - timedelta(days=days)
        titles = (
            TagMember.objects.filter(created_time__gt=t)
            .filter(parent__visibility=0)
            .annotate(title=F("parent__title"))
            .values("title")
            .annotate(total=Count("parent_id", distinct=True))
            .order_by("-total")
            .values_list("title", flat=True)
        )
        return titles

    def get_item_tags(self, item: Item):
        return sorted(
            TagMember.objects.filter(parent__owner=self.owner, item=item).values_list(
                "parent__title", flat=True
            )
        )
