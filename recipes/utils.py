import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from django.conf import settings

class ValidationError(Exception):
    pass

def dict_to_json(recipe: dict) -> str:
    return json.dumps(recipe, ensure_ascii=False, indent=2)

def dict_to_xml(recipe: dict) -> str:
    root = ET.Element('recipe')
    ET.SubElement(root, 'title').text = recipe['title']
    ET.SubElement(root, 'author').text = recipe['author']
    ET.SubElement(root, 'category').text = recipe['category']
    ET.SubElement(root, 'cooking_time').text = str(recipe['cooking_time'])
    ingr_parent = ET.SubElement(root, 'ingredients')
    for ing in recipe['ingredients']:
        ET.SubElement(ingr_parent, 'ingredient').text = ing
    ET.SubElement(root, 'description').text = recipe.get('description', '')
    return ET.tostring(root, encoding='unicode')

def validate_recipe_dict(data: dict):
    required = ['title', 'author', 'category', 'cooking_time', 'ingredients']
    for field in required:
        if field not in data:
            raise ValidationError(f'Отсутствует обязательное поле: {field}')
    if not isinstance(data['cooking_time'], int) or not (1 <= data['cooking_time'] <= 1440):
        raise ValidationError('Поле "cooking_time" должно быть целым числом 1..1440.')

def parse_json_file(path: Path) -> dict:
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError(f'Некорректный JSON: {exc}')
    validate_recipe_dict(data)
    return data

def parse_xml_file(path: Path) -> dict:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise ValidationError(f'Некорректный XML: {exc}')
    root = tree.getroot()
    def get_text(tag):
        el = root.find(tag)
        if el is None or el.text is None or not el.text.strip():
            raise ValidationError(f'Отсутствует тег <{tag}>.')
        return el.text.strip()
    ingr_parent = root.find('ingredients')
    ingredients = [i.text.strip() for i in ingr_parent.findall('ingredient') if i.text] if ingr_parent is not None else []
    data = {
        'title': get_text('title'),
        'author': get_text('author'),
        'category': get_text('category'),
        'cooking_time': int(get_text('cooking_time')),
        'ingredients': ingredients,
        'description': (root.findtext('description') or '').strip(),
    }
    validate_recipe_dict(data)
    return data

def safe_filename(ext: str) -> str:
    return f"{uuid.uuid4().hex}{ext}"

def save_recipe_file(recipe: dict, fmt: str) -> Path:
    if fmt == 'json':
        directory, ext, content = settings.JSON_DIR, '.json', dict_to_json(recipe)
    else:
        directory, ext, content = settings.XML_DIR, '.xml', dict_to_xml(recipe)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / safe_filename(ext)
    path.write_text(content, encoding='utf-8')
    return path
    