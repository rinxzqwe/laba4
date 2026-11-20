from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from .forms import RecipeForm
from .models import Recipe
from .utils import (
    ValidationError, parse_json_file, parse_xml_file,
    safe_filename, save_recipe_file,
)

#  ДОБАВЛЕНИЕ РЕЦЕПТА
@require_http_methods(["GET", "POST"])
def recipe_create(request):
    if request.method == 'POST':
        form = RecipeForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            # Сохранение в БД
            if data['save_to'] == 'db':
                try:
                    Recipe.objects.create(
                        title=data['title'], author=data['author'], category=data['category'],
                        cooking_time=data['cooking_time'], ingredients=", ".join(data['ingredients']),
                        description=data['description']
                    )
                    messages.success(request, 'Рецепт успешно сохранен в базу данных!')
                except IntegrityError:
                    messages.error(request, 'Ошибка: Такой рецепт уже есть в базе данных.')
            # Сохранение в файл
            else:
                recipe_dict = {
                    'title': data['title'], 'author': data['author'], 'category': data['category'],
                    'cooking_time': data['cooking_time'], 'ingredients': data['ingredients'],
                    'description': data['description'],
                }
                fmt = data.get('file_format', 'json')
                try:
                    path = save_recipe_file(recipe_dict, fmt)
                    messages.success(request, f'Рецепт сохранен в файл {fmt.upper()} ({path.name}).')
                except Exception as exc:
                    messages.error(request, f'Ошибка сохранения файла: {exc}')
            return redirect('recipe_create')
    else:
        form = RecipeForm()
    return render(request, 'recipes/recipe_form.html', {'form': form})

# ЗАГРУЗКА ФАЙЛОВ 
@require_http_methods(["GET", "POST"])
def upload_file(request):
    if request.method == 'POST':
        uploaded = request.FILES.get('data_file')
        if not uploaded:
            messages.error(request, 'Файл не выбран.')
            return redirect('upload_file')
        
        suffix = Path(uploaded.name).suffix.lower()
        if suffix not in settings.ALLOWED_EXTENSIONS:
            messages.error(request, 'Допустимы только .json и .xml.')
            return redirect('upload_file')
            
        new_name = safe_filename(suffix)
        directory = settings.JSON_DIR if suffix == '.json' else settings.XML_DIR
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / new_name
        
        with path.open('wb') as f:
            for chunk in uploaded.chunks(): f.write(chunk)
            
        try:
            if suffix == '.json': parse_json_file(path)
            else: parse_xml_file(path)
        except ValidationError as exc:
            path.unlink(missing_ok=True)
            messages.error(request, f'Файл не прошел проверку и удален: {exc}')
        else:
            messages.success(request, f'Файл успешно загружен: {new_name}')
        return redirect('upload_file')
    return render(request, 'recipes/upload.html')

# ПРОСМОТР ВСЕХ ДАННЫХ (ВЫБОР ИСТОЧНИКА) 
def file_list(request):
    source = request.GET.get('source', 'files') # 'files' или 'db'
    context = {'source': source, 'files': [], 'recipes': []}

    if source == 'db':
        context['recipes'] = Recipe.objects.all().order_by('-id')
    else:
        # Логика чтения файлов
        for directory, fmt in ((settings.JSON_DIR, 'JSON'), (settings.XML_DIR, 'XML')):
            if not directory.exists(): continue
            for path in sorted(directory.iterdir()):
                if path.is_file() and not path.name.startswith('.'):
                    try:
                        data = parse_json_file(path) if path.suffix == '.json' else parse_xml_file(path)
                        context['files'].append({'filename': path.name, 'format': fmt, 'data': data, 'error': None})
                    except ValidationError as exc:
                        context['files'].append({'filename': path.name, 'format': fmt, 'data': None, 'error': str(exc)})
    return render(request, 'recipes/list_files.html', context)

# 4. AJAX ПОИСК
def search_recipes(request):
    query = request.GET.get('q', '')
    # Поиск по названию или автору
    recipes = Recipe.objects.filter(title__icontains=query) | Recipe.objects.filter(author__icontains=query)
    data = list(recipes.values('id', 'title', 'author', 'category', 'cooking_time', 'ingredients', 'description'))
    return JsonResponse({'recipes': data})

# РЕДАКТИРОВАНИЕ 
def edit_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if request.method == 'POST':
        form = RecipeForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            recipe.title = data['title']
            recipe.author = data['author']
            recipe.category = data['category']
            recipe.cooking_time = data['cooking_time']
            recipe.ingredients = ", ".join(data['ingredients'])
            recipe.description = data['description']
            try:
                recipe.save()
                messages.success(request, 'Рецепт успешно обновлен!')
                return redirect(f'/files/?source=db')
            except IntegrityError:
                messages.error(request, 'Ошибка: Рецепт с такими данными уже существует.')
    else:
        # Заполняем форму текущими данными
        initial_data = {
            'title': recipe.title, 'author': recipe.author, 'category': recipe.category,
            'cooking_time': recipe.cooking_time, 'ingredients': recipe.ingredients,
            'description': recipe.description, 'save_to': 'db'
        }
        form = RecipeForm(initial=initial_data)
    return render(request, 'recipes/recipe_form.html', {'form': form, 'is_edit': True})

# УДАЛЕНИЕ (AJAX)
@csrf_exempt
def delete_recipe(request, pk):
    if request.method == 'POST':
        recipe = get_object_or_404(Recipe, pk=pk)
        recipe.delete()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)