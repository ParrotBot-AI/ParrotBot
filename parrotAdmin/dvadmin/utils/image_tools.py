from base64 import b64decode, b64encode
from hashlib import sha1
from django.core.files.base import ContentFile
from django.http import QueryDict


def base64_to_image(data):
    meta, img = data.split(";base64,")
    ext = meta.split("/")[-1]
    fname = sha1(img.encode()).hexdigest()
    return ContentFile(b64decode(img), name=f"{fname}.{ext}")


def separate_avatar_field(data):
    if isinstance(data, QueryDict):
        data = data.dict()
    avatar = data.pop("avatar") if "avatar" in data else None
    return data, avatar


def save_new_avatar(instance, avatar_str, delete_on_fail=False):
    if avatar_str is None:
        return True
    try:
        instance.avatar = base64_to_image(avatar_str)
        instance.save()
        return True
    except:
        if delete_on_fail:
            # should only reach here when the instance is just created
            instance.delete()
        return False