from __future__ import unicode_literals

import slugid

from django.db import models


class ViewConf(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    uuid = models.CharField(max_length=100, unique=True, default=slugid.nice)
    viewconf = models.TextField()

    class Meta:
        ordering = ('created',)


class Tileset(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    uuid = models.CharField(max_length=100, unique=True, default=slugid.nice)
    datafile = models.FileField(upload_to='uploads')
    filetype = models.TextField()
    datatype = models.TextField(default='unknown')

    coordSystem = models.TextField()
    coordSystem2 = models.TextField(default='')

    owner = models.ForeignKey(
        'auth.User', related_name='tilesets', on_delete=models.CASCADE
    )
    private = models.BooleanField(default=False)
    name = models.TextField(blank=True)

    class Meta:
        ordering = ('created',)
        permissions = (('view_tileset', "View tileset"),)
