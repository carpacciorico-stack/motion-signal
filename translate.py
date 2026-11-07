import json, re
from pathlib import Path
import argostranslate.package
import argostranslate.translate

ROOT = Path(__file__).resolve().parent
path = ROOT / 'articles.json'
data = json.loads(path.read_text())
argostranslate.package.update_package_index()
packages = argostranslate.package.get_available_packages()
pkg = next(p for p in packages if p.from_code == 'en' and p.to_code == 'ja')
argostranslate.package.install_from_path(pkg.download())
for article in data['articles']:
    for field in ('title', 'summary'):
        original = article.get(field, '')
        if field == 'summary':
            original = re.sub(r'\s*submitted by\s.*', '', original, flags=re.I).strip(' .')
        article[field + '_original'] = original
        if not original:
            article[field + '_ja'] = '本文の抜粋がありません。元記事をご確認ください。'
        elif re.search(r'[ぁ-んァ-ン]', original):
            article[field + '_ja'] = original
        else:
            article[field + '_ja'] = argostranslate.translate.translate(original, 'en', 'ja')
    article['translation'] = 'argos_machine_translation'
data['notice'] = 'タイトル・RSSの抜粋を日本語に自動翻訳しています。誤訳や省略があるため、詳細は原文をご確認ください。評価はキーワードによる自動判定です。'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print('Japanese translations:', len(data['articles']))
