from django.contrib import admin

from guardian.admin import GuardedModelAdmin

from tilesets.models import Tileset


class TilesetAdmin(GuardedModelAdmin):
    list_display = [
        'created',
        'uuid',
        'datafile',
        'filetype',
        'datatype',
        'coordSystem',
        'coordSystem2',
        'owner',
        'private',
        'name',
    ]


admin.site.register(Tileset, TilesetAdmin)
