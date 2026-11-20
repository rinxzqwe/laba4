from django.db import models

class Recipe(models.Model):
    title = models.CharField(max_length=100, verbose_name="Название")
    author = models.CharField(max_length=100, verbose_name="Автор")
    category = models.CharField(max_length=50, verbose_name="Категория")
    cooking_time = models.IntegerField(verbose_name="Время готовки (мин)")
    ingredients = models.TextField(verbose_name="Ингредиенты (через запятую)")
    description = models.TextField(blank=True, default='', verbose_name="Описание")

    def __str__(self):
        return self.title

    class Meta:
        # Проверка на дубликаты на уровне БД
        unique_together = ('title', 'author', 'category', 'cooking_time', 'ingredients')