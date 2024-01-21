import io
from typing import TYPE_CHECKING

import blurhash
from django.conf import settings
from django.core.cache import cache
from django.core.files.images import ImageFile
from PIL import Image

from .models import *

if TYPE_CHECKING:
    from journal.models import Collection
    from users.models import APIdentity
    from users.models import User as NeoUser


def _int(s: str):
    try:
        return int(s)
    except:
        return -1


def _rating_to_emoji(score: int, star_mode=0):
    """convert score(0~10) to mastodon star emoji code"""
    if score is None or score == "" or score == 0:
        return ""
    solid_stars = score // 2
    half_star = int(bool(score % 2))
    empty_stars = 5 - solid_stars if not half_star else 5 - solid_stars - 1
    if star_mode == 1:
        emoji_code = "🌕" * solid_stars + "🌗" * half_star + "🌑" * empty_stars
    else:
        emoji_code = (
            settings.STAR_SOLID * solid_stars
            + settings.STAR_HALF * half_star
            + settings.STAR_EMPTY * empty_stars
        )
    emoji_code = emoji_code.replace("::", ": :")
    emoji_code = " " + emoji_code + " "
    return emoji_code


class Takahe:
    Visibilities = Post.Visibilities

    @staticmethod
    def get_domain():
        domain = settings.SITE_INFO["site_domain"]
        d = Domain.objects.filter(domain=domain).first()
        if not d:
            logger.info(f"Creating takahe domain {domain}")
            d = Domain.objects.create(
                domain=domain,
                local=True,
                service_domain=None,
                notes="NeoDB",
                nodeinfo=None,
            )
        return d

    @staticmethod
    def get_node_name_for_domain(d: str):
        domain = Domain.objects.filter(domain=d).first()
        if domain and domain.nodeinfo:
            return domain.nodeinfo.get("metadata", {}).get("nodeName")

    @staticmethod
    def sync_password(u: "NeoUser"):
        user = User.objects.filter(pk=u.pk).first()
        if not user:
            raise ValueError(f"Cannot find takahe user {u}")
        elif user.password != u.password:
            logger.info(f"Updating takahe user {u} password")
            user.password = u.password
            user.save()

    @staticmethod
    def init_identity_for_local_user(u: "NeoUser"):
        """
        When a new local NeoDB user is created,
        create a takahe user with the NeoDB user pk,
        create a takahe identity,
        then create a NeoDB APIdentity with the takahe identity pk.
        """
        from users.models import APIdentity

        logger.info(f"User {u} initialize identity")
        if not u.username:
            logger.warning(f"User {u} has no username")
            return None
        user = User.objects.filter(pk=u.pk).first()
        handler = "@" + u.username
        if not user:
            logger.info(f"Creating takahe user {u}")
            user = User.objects.create(pk=u.pk, email=handler, password=u.password)
        else:
            if user.email != handler:
                logger.warning(f"Updating takahe user {u} email to {handler}")
                user.email = handler
                user.save()
        domain = Domain.objects.get(domain=settings.SITE_INFO["site_domain"])
        identity = Identity.objects.filter(username=u.username, local=True).first()
        if not identity:
            logger.info(f"Creating takahe identity {u}@{domain}")
            identity = Identity.objects.create(
                actor_uri=f"https://{domain.uri_domain}/@{u.username}@{domain.domain}/",
                profile_uri=u.absolute_url,
                username=u.username,
                domain=domain,
                name=u.username,
                local=True,
                discoverable=True,
            )
            identity.generate_keypair()
            identity.ensure_uris()
        if not user.identities.filter(pk=identity.pk).exists():
            user.identities.add(identity)
        apidentity = APIdentity.objects.filter(pk=identity.pk).first()
        if not apidentity:
            logger.info(f"Creating APIdentity for {identity}")
            apidentity = APIdentity.objects.create(
                user=u,
                id=identity.pk,
                local=True,
                username=u.username,
                domain_name=domain.domain,
                deleted=identity.deleted,
            )
        elif apidentity.username != identity.username:
            logger.warning(
                f"Updating APIdentity {apidentity} username to {identity.username}"
            )
            apidentity.username = identity.username
            apidentity.save()
        if u.identity != apidentity:
            logger.warning(f"Linking user {u} identity to {apidentity}")
            u.identity = apidentity
            u.save(update_fields=["identity"])
        return apidentity

    @staticmethod
    def get_identity_by_handler(username: str, domain: str) -> Identity | None:
        return Identity.objects.filter(
            username__iexact=username, domain__domain__iexact=domain
        ).first()

    @staticmethod
    def delete_identity(identity_pk: int):
        identity = Identity.objects.filter(pk=identity_pk).first()
        if not identity:
            logger.warning(f"Cannot find identity {identity_pk}")
            return
        logger.warning(f"Deleting identity {identity}")
        identity.state = "deleted"
        identity.deleted = timezone.now()
        identity.state_next_attempt = timezone.now()
        identity.save()

    @staticmethod
    def create_internal_message(message: dict):
        InboxMessage.create_internal(message)

    @staticmethod
    def fetch_remote_identity(handler: str) -> int | None:
        InboxMessage.create_internal({"type": "FetchIdentity", "handle": handler})

    @staticmethod
    def get_identity(pk: int):
        return Identity.objects.get(pk=pk)

    @staticmethod
    def get_identity_by_local_user(u: "NeoUser"):
        return (
            Identity.objects.filter(pk=u.identity.pk, local=True).first()
            if u and u.is_authenticated and u.identity
            else None
        )

    @staticmethod
    def get_or_create_remote_apidentity(identity: Identity):
        from users.models import APIdentity

        apid = APIdentity.objects.filter(pk=identity.pk).first()
        if not apid:
            if identity.local:
                raise ValueError(f"local takahe identity {identity} missing APIdentity")
            if not identity.domain_id:
                raise ValueError(f"remote takahe identity {identity} missing domain")
            apid = APIdentity.objects.get_or_create(
                id=identity.pk,
                defaults={
                    "user": None,
                    "local": False,
                    "username": identity.username,
                    "domain_name": identity.domain_id,
                    "deleted": identity.deleted,
                    "anonymous_viewable": False,
                },
            )[0]
        return apid

    @staticmethod
    def get_local_user_by_identity(identity: Identity):
        from users.models import User as NeoUser

        return NeoUser.objects.get(identity_id=identity.pk) if identity.local else None

    @staticmethod
    def get_is_following(identity_pk: int, target_pk: int):
        return Follow.objects.filter(
            source_id=identity_pk, target_id=target_pk, state="accepted"
        ).exists()

    @staticmethod
    def get_is_follow_requesting(identity_pk: int, target_pk: int):
        return Follow.objects.filter(
            source_id=identity_pk,
            target_id=target_pk,
            state__in=["unrequested", "pending_approval"],
        ).exists()

    @staticmethod
    def get_is_muting(identity_pk: int, target_pk: int):
        return Block.objects.filter(
            source_id=identity_pk,
            target_id=target_pk,
            state__in=["new", "sent", "awaiting_expiry"],
            mute=True,
        ).exists()

    @staticmethod
    def get_is_blocking(identity_pk: int, target_pk: int):
        return Block.objects.filter(
            source_id=identity_pk,
            target_id=target_pk,
            state__in=["new", "sent", "awaiting_expiry"],
            mute=False,
        ).exists()

    @staticmethod
    def get_following_ids(identity_pk: int):
        targets = Follow.objects.filter(
            source_id=identity_pk, state="accepted"
        ).values_list("target", flat=True)
        return list(targets)

    @staticmethod
    def get_follower_ids(identity_pk: int):
        targets = Follow.objects.filter(
            target_id=identity_pk, state="accepted"
        ).values_list("source", flat=True)
        return list(targets)

    @staticmethod
    def get_following_request_ids(identity_pk: int):
        targets = Follow.objects.filter(
            source_id=identity_pk, state__in=["unrequested", "pending_approval"]
        ).values_list("target", flat=True)
        return list(targets)

    @staticmethod
    def get_requested_follower_ids(identity_pk: int):
        targets = Follow.objects.filter(
            target_id=identity_pk, state="pending_approval"
        ).values_list("source", flat=True)
        return list(targets)

    @staticmethod
    def update_follow_state(
        source_pk: int, target_pk: int, from_states: list[str], to_state: str
    ):
        follow = Follow.objects.filter(source_id=source_pk, target_id=target_pk).first()
        if (
            follow
            and (not from_states or follow.state in from_states)
            and follow.state != to_state
        ):
            follow.state = to_state
            follow.save()
        return follow

    @staticmethod
    def follow(source_pk: int, target_pk: int, force_accept: bool = False):
        try:
            follow = Follow.objects.get(source_id=source_pk, target_id=target_pk)
            if follow.state != "accepted":
                follow.state = "accepted" if force_accept else "unrequested"
                follow.save()
        except Follow.DoesNotExist:
            source = Identity.objects.get(pk=source_pk)
            follow = Follow.objects.create(
                source_id=source_pk,
                target_id=target_pk,
                boosts=True,
                uri="",
                state="accepted" if force_accept else "unrequested",
            )
            follow.uri = source.actor_uri + f"follow/{follow.pk}/"
            follow.save()

    @staticmethod
    def unfollow(source_pk: int, target_pk: int):
        Takahe.update_follow_state(source_pk, target_pk, [], "undone")
        # InboxMessage.create_internal(
        #     {
        #         "type": "ClearTimeline",
        #         "object": target_identity.pk,
        #         "actor": self.identity.pk,
        #     }
        # )

    @staticmethod
    def accept_follow_request(source_pk: int, target_pk: int):
        Takahe.update_follow_state(source_pk, target_pk, [], "accepting")

    @staticmethod
    def reject_follow_request(source_pk: int, target_pk: int):
        Takahe.update_follow_state(source_pk, target_pk, [], "rejecting")

    @staticmethod
    def get_muting_ids(identity_pk: int) -> list[int]:
        targets = Block.objects.filter(
            source_id=identity_pk,
            mute=True,
            state__in=["new", "sent", "awaiting_expiry"],
        ).values_list("target", flat=True)
        return list(targets)

    @staticmethod
    def get_blocking_ids(identity_pk: int) -> list[int]:
        targets = Block.objects.filter(
            source_id=identity_pk,
            mute=False,
            state__in=["new", "sent", "awaiting_expiry"],
        ).values_list("target", flat=True)
        return list(targets)

    @staticmethod
    def get_rejecting_ids(identity_pk: int) -> list[int]:
        pks1 = Block.objects.filter(
            source_id=identity_pk,
            mute=False,
            state__in=["new", "sent", "awaiting_expiry"],
        ).values_list("target", flat=True)
        pks2 = Block.objects.filter(
            target_id=identity_pk,
            mute=False,
            state__in=["new", "sent", "awaiting_expiry"],
        ).values_list("source", flat=True)
        return list(set(list(pks1) + list(pks2)))

    @staticmethod
    def block_or_mute(source_pk: int, target_pk: int, is_mute: bool):
        source = Identity.objects.get(pk=source_pk)
        if not source.local:
            raise ValueError(f"Cannot block/mute from remote identity {source}")
        with transaction.atomic():
            block, _ = Block.objects.update_or_create(
                defaults={"state": "new"},
                source_id=source_pk,
                target_id=target_pk,
                mute=is_mute,
            )
            if block.state != "new" or not block.uri:
                block.state = "new"
                block.uri = source.actor_uri + f"block/{block.pk}/"
                block.save()
            if not is_mute:
                Takahe.unfollow(source_pk, target_pk)
                Takahe.reject_follow_request(target_pk, source_pk)
            return block

    @staticmethod
    def undo_block_or_mute(source_pk: int, target_pk: int, is_mute: bool):
        Block.objects.filter(
            source_id=source_pk, target_id=target_pk, mute=is_mute
        ).update(state="undone")

    @staticmethod
    def block(source_pk: int, target_pk: int):
        return Takahe.block_or_mute(source_pk, target_pk, False)

    @staticmethod
    def unblock(source_pk: int, target_pk: int):
        return Takahe.undo_block_or_mute(source_pk, target_pk, False)

    @staticmethod
    def mute(source_pk: int, target_pk: int):
        return Takahe.block_or_mute(source_pk, target_pk, True)

    @staticmethod
    def unmute(source_pk: int, target_pk: int):
        return Takahe.undo_block_or_mute(source_pk, target_pk, True)

    @staticmethod
    def _force_state_cycle():  # for unit testing only
        Follow.objects.filter(
            state__in=["rejecting", "undone", "pending_removal"]
        ).delete()
        Follow.objects.all().update(state="accepted")
        Block.objects.filter(state="new").update(state="sent")
        Block.objects.exclude(state="sent").delete()

    @staticmethod
    def upload_image(
        author_pk: int,
        filename: str,
        content: bytes,
        mimetype: str,
        description: str = "",
    ) -> PostAttachment:
        if len(content) > 1024 * 1024 * 5:
            raise ValueError("Image too large")
        main_file = ImageFile(io.BytesIO(content), name=filename)
        resized_image = Image.open(io.BytesIO(content))
        resized_image.thumbnail((400, 225), resample=Image.Resampling.BILINEAR)
        new_image_bytes = io.BytesIO()
        resized_image.save(new_image_bytes, format="webp", save_all=True)
        thumbnail_file = ImageFile(new_image_bytes, name="image.webp")
        hash = blurhash.encode(resized_image, 4, 4)
        attachment = PostAttachment.objects.create(
            mimetype=mimetype,
            width=main_file.width,
            height=main_file.height,
            name=description or None,
            state="fetched",
            author_id=author_pk,
            file=main_file,
            thumbnail=thumbnail_file,
            blurhash=hash,
        )
        attachment.save()
        return attachment

    @staticmethod
    def post(
        author_pk: int,
        pre_conetent: str,
        content: str,
        visibility: Visibilities,
        summary: str | None = None,
        sensitive: bool = False,
        data: dict | None = None,
        post_pk: int | None = None,
        post_time: datetime.datetime | None = None,
        reply_to_pk: int | None = None,
        attachments: list | None = None,
    ) -> Post | None:
        identity = Identity.objects.get(pk=author_pk)
        post = (
            Post.objects.filter(author=identity, pk=post_pk).first()
            if post_pk
            else None
        )
        if post_pk and not post:
            raise ValueError(f"Cannot find post to edit: {post_pk}")
        reply_to_post = (
            Post.objects.filter(pk=reply_to_pk).first() if reply_to_pk else None
        )
        if reply_to_pk and not reply_to_post:
            raise ValueError(f"Cannot find post to reply: {reply_to_pk}")
        if post:
            post.edit_local(
                pre_conetent,
                content,
                summary,
                sensitive,
                visibility=visibility,
                type_data=data,
                published=post_time,
                attachments=attachments,
            )
        else:
            post = Post.create_local(
                identity,
                pre_conetent,
                content,
                summary,
                sensitive,
                visibility=visibility,
                type_data=data,
                published=post_time,
                reply_to=reply_to_post,
                attachments=attachments,
            )
        return post

    @staticmethod
    def get_post(post_pk: int) -> Post | None:
        return Post.objects.filter(pk=post_pk).first()

    @staticmethod
    def get_posts(post_pks: list[int]):
        return Post.objects.filter(pk__in=post_pks)

    @staticmethod
    def get_post_url(post_pk: int) -> str | None:
        post = Post.objects.filter(pk=post_pk).first() if post_pk else None
        return post.object_uri if post else None

    @staticmethod
    def delete_posts(post_pks):
        Post.objects.filter(pk__in=post_pks).update(state="deleted")
        # TimelineEvent.objects.filter(subject_post__in=[post.pk]).delete()
        PostInteraction.objects.filter(post__in=post_pks).update(state="undone")

    @staticmethod
    def get_spoiler_text(text, item):
        if text and text.find(">!") != -1:
            spoiler_text = f"关于《{item.display_title}》 可能有关键情节等敏感内容"
            return spoiler_text, text.replace(">!", "").replace("!<", "")
        else:
            return None, text or ""

    @staticmethod
    def visibility_n2t(visibility: int, post_public_mode: int) -> Visibilities:
        if visibility == 1:
            return Takahe.Visibilities.followers
        elif visibility == 2:
            return Takahe.Visibilities.mentioned
        elif post_public_mode == 4:
            return Takahe.Visibilities.local_only
        elif post_public_mode == 1:
            return Takahe.Visibilities.unlisted
        else:
            return Takahe.Visibilities.public

    @staticmethod
    def post_collection(collection: "Collection"):
        existing_post = collection.latest_post
        user = collection.owner.user
        if not user:
            raise ValueError(f"Cannot find user for collection {collection}")
        visibility = Takahe.visibility_n2t(
            collection.visibility, user.preference.post_public_mode
        )
        if existing_post and visibility != existing_post.visibility:
            Takahe.delete_posts([existing_post.pk])
            existing_post = None
        data = {
            "object": {
                # "tag": [item.ap_object_ref for item in collection.items],
                "relatedWith": [collection.ap_object],
            }
        }
        if existing_post and existing_post.type_data == data:
            return existing_post
        action_label = "创建"
        category = "收藏单"
        item_link = collection.absolute_url
        pre_conetent = (
            f'{action_label}{category} <a href="{item_link}">{collection.title}</a><br>'
        )
        content = collection.plain_content
        if len(content) > 360:
            content = content[:357] + "..."
        data = {
            "object": {
                # "tag": [item.ap_object_ref for item in collection.items],
                "relatedWith": [collection.ap_object],
            }
        }
        post = Takahe.post(
            collection.owner.pk,
            pre_conetent,
            content,
            visibility,
            None,
            False,
            data,
            existing_post.pk if existing_post else None,
            collection.created_time,
        )
        if not post:
            return
        collection.link_post_id(post.pk)
        return post

    @staticmethod
    def post_comment(comment, share_as_new_post: bool) -> Post | None:
        from catalog.common import ItemCategory

        user = comment.owner.user
        category = str(ItemCategory(comment.item.category).label)
        tags = (
            "\n" + user.preference.mastodon_append_tag.replace("[category]", category)
            if user.preference.mastodon_append_tag
            else ""
        )
        item_link = f"{settings.SITE_INFO['site_url']}/~neodb~{comment.item_url}"
        action_label = "评论" if comment.text else "分享"
        pre_conetent = f'{action_label}{category} <a href="{item_link}">{comment.item.display_title}</a><br>'
        spoiler, txt = Takahe.get_spoiler_text(comment.text, comment.item)
        content = f"{txt}\n{tags}"
        data = {
            "object": {
                "tag": [comment.item.ap_object_ref],
                "relatedWith": [comment.ap_object],
            }
        }
        v = Takahe.visibility_n2t(comment.visibility, user.preference.post_public_mode)
        existing_post = None if share_as_new_post else comment.latest_post
        post = Takahe.post(
            comment.owner.pk,
            pre_conetent,
            content,
            v,
            spoiler,
            spoiler is not None,
            data,
            existing_post.pk if existing_post else None,
            comment.created_time,
        )
        if not post:
            return
        comment.link_post_id(post.pk)
        return post

    @staticmethod
    def post_review(review, share_as_new_post: bool) -> Post | None:
        from catalog.common import ItemCategory

        user = review.owner.user
        tags = (
            "\n"
            + user.preference.mastodon_append_tag.replace(
                "[category]", str(ItemCategory(review.item.category).label)
            )
            if user.preference.mastodon_append_tag
            else ""
        )
        stars = _rating_to_emoji(review.rating_grade, 1)
        item_link = f"{settings.SITE_INFO['site_url']}/~neodb~{review.item.url}"

        pre_conetent = f'发布了关于 <a href="{item_link}">{review.item.display_title}</a> 的评论：<br><a href="{review.absolute_url}">{review.title}</a>'
        content = f"{stars}\n{tags}"
        data = {
            "object": {
                "tag": [review.item.ap_object_ref],
                "relatedWith": [review.ap_object],
            }
        }
        v = Takahe.visibility_n2t(review.visibility, user.preference.post_public_mode)
        existing_post = None if share_as_new_post else review.latest_post
        post = Takahe.post(  # TODO post as Article?
            review.owner.pk,
            pre_conetent,
            content,
            v,
            None,
            False,
            data,
            existing_post.pk if existing_post else None,
            review.created_time,
        )
        if not post:
            return
        review.link_post_id(post.pk)
        return post

    @staticmethod
    def post_mark(mark, share_as_new_post: bool, append_content="") -> Post | None:
        from catalog.common import ItemCategory

        user = mark.owner.user
        tags = (
            user.preference.mastodon_append_tag.replace(
                "[category]", str(ItemCategory(mark.item.category).label)
            )
            + "\n"
            if user.preference.mastodon_append_tag
            else ""
        )
        stars = _rating_to_emoji(mark.rating_grade, 1)
        item_link = f"{settings.SITE_INFO['site_url']}/~neodb~{mark.item.url}"
        action = mark.action_label_for_feed
        pre_conetent = f'{action} <a href="{item_link}">{mark.item.display_title}</a>'
        spoiler, txt = Takahe.get_spoiler_text(mark.comment_text, mark.item)
        content = f"{stars} \n{txt}\n{tags}"
        data = {
            "object": {
                "tag": [mark.item.ap_object_ref],
                "relatedWith": [mark.shelfmember.ap_object],
            }
        }
        if mark.comment:
            data["object"]["relatedWith"].append(mark.comment.ap_object)
        if mark.rating:
            data["object"]["relatedWith"].append(mark.rating.ap_object)
        v = Takahe.visibility_n2t(mark.visibility, user.preference.post_public_mode)
        existing_post = (
            None
            if share_as_new_post
            or mark.shelfmember.latest_post is None
            or mark.shelfmember.latest_post.state in ["deleted", "deleted_fanned_out"]
            else mark.shelfmember.latest_post
        )
        post = Takahe.post(
            mark.owner.pk,
            pre_conetent,
            content + append_content,
            v,
            spoiler,
            spoiler is not None,
            data,
            existing_post.pk if existing_post else None,
            mark.shelfmember.created_time,
        )
        if not post:
            return
        for piece in [mark.shelfmember, mark.comment, mark.rating]:
            if piece:
                piece.link_post_id(post.pk)
        return post

    @staticmethod
    def interact_post(post_pk: int, identity_pk: int, type: str):
        post = Post.objects.filter(pk=post_pk).first()
        if not post:
            logger.warning(f"Cannot find post {post_pk}")
            return
        identity = Identity.objects.filter(pk=identity_pk).first()
        if not identity:
            logger.warning(f"Cannot find identity {identity_pk}")
            return
        interaction = PostInteraction.objects.get_or_create(
            type=type,
            identity_id=identity_pk,
            post=post,
        )[0]
        if interaction.state not in ["new", "fanned_out"]:
            interaction.state = "new"
            interaction.save()
        post.calculate_stats()
        return interaction

    @staticmethod
    def uninteract_post(post_pk: int, identity_pk: int, type: str):
        post = Post.objects.filter(pk=post_pk).first()
        if not post:
            logger.warning(f"Cannot find post {post_pk}")
            return
        for interaction in PostInteraction.objects.filter(
            type=type,
            identity_id=identity_pk,
            post=post,
        ):
            interaction.state = "undone"
            interaction.save()
        post.calculate_stats()

    @staticmethod
    def reply_post(
        post_pk: int, identity_pk: int, content: str, visibility: Visibilities
    ):
        return Takahe.post(identity_pk, "", content, visibility, reply_to_pk=post_pk)

    @staticmethod
    def boost_post(post_pk: int, identity_pk: int):
        return Takahe.interact_post(post_pk, identity_pk, "boost")

    @staticmethod
    def post_boosted_by(post_pk: int, identity_pk: int) -> bool:
        interaction = Takahe.get_user_interaction(post_pk, identity_pk, "boost")
        return interaction is not None and interaction.state in ["new", "fanned_out"]

    @staticmethod
    def like_post(post_pk: int, identity_pk: int):
        return Takahe.interact_post(post_pk, identity_pk, "like")

    @staticmethod
    def unlike_post(post_pk: int, identity_pk: int):
        return Takahe.uninteract_post(post_pk, identity_pk, "like")

    @staticmethod
    def post_liked_by(post_pk: int, identity_pk: int) -> bool:
        interaction = Takahe.get_user_interaction(post_pk, identity_pk, "like")
        return interaction is not None and interaction.state in ["new", "fanned_out"]

    @staticmethod
    def get_user_interaction(post_pk: int, identity_pk: int, type: str):
        if not post_pk or not identity_pk:
            return None
        post = Post.objects.filter(pk=post_pk).first()
        if not post:
            logger.warning(f"Cannot find post {post_pk}")
            return None
        return PostInteraction.objects.filter(
            type=type,
            identity_id=identity_pk,
            post=post,
        ).first()

    @staticmethod
    def get_post_stats(post_pk: int) -> dict:
        post = Post.objects.filter(pk=post_pk).first()
        if not post:
            logger.warning(f"Cannot find post {post_pk}")
            return {}
        return post.stats or {}

    @staticmethod
    def get_replies_for_posts(post_pks: list[int], identity_pk: int | None):
        post_uris = Post.objects.filter(pk__in=post_pks).values_list(
            "object_uri", flat=True
        )
        if not post_uris.exists():
            return Post.objects.none()
        identity = (
            Identity.objects.filter(pk=identity_pk).first() if identity_pk else None
        )
        child_queryset = (
            Post.objects.not_hidden()
            .prefetch_related(
                # "attachments",
                "mentions",
                "emojis",
            )
            .select_related(
                "author",
                "author__domain",
            )
            .filter(in_reply_to__in=post_uris)
            .order_by("published")
        )
        if identity:
            child_queryset = child_queryset.visible_to(
                identity=identity, include_replies=True
            )
        else:
            child_queryset = child_queryset.unlisted(include_replies=True)
        return child_queryset

    @staticmethod
    def html2txt(html: str) -> str:
        if not html:
            return ""
        return FediverseHtmlParser(html).plain_text

    @staticmethod
    def txt2html(txt: str) -> str:
        if not txt:
            return ""
        return FediverseHtmlParser(linebreaks_filter(txt)).html

    @staticmethod
    def update_state(obj, state):
        obj.state = state
        obj.state_changed = timezone.now()
        obj.state_next_attempt = None
        obj.state_locked_until = None
        obj.save(
            update_fields=[
                "state",
                "state_changed",
                "state_next_attempt",
                "state_locked_until",
            ]
        )

    @staticmethod
    def get_neodb_peers():
        cache_key = "neodb_peers"
        peers = cache.get(cache_key, None)
        if peers is None:
            peers = list(
                Domain.objects.filter(
                    nodeinfo__protocols__contains="neodb", local=False
                ).values_list("pk", flat=True)
            )
            cache.set(cache_key, peers, timeout=1800)
        return peers

    @staticmethod
    def verify_invite(token):
        if not token:
            return False
        invite = Invite.objects.filter(token=token).first()
        return invite and invite.valid
