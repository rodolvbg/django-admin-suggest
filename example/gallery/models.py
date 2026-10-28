from django.db import models


class Album(models.Model):
    title = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.title


class Image(models.Model):
    album = models.ForeignKey(Album, related_name="images", on_delete=models.CASCADE)
    title = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.title
