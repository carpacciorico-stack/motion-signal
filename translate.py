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
TERMS = {'after effects':'AE', 'procreate dreams':'Procreate Dreams', 'adjustment layer':'調整レイヤー', 'keyframe':'キーフレーム', 'aescripts':'aescripts', 'expression':'エクスプレッション', 'rotoscope':'ロトスコープ'}
TITLES = {
'Recently learned and used after effects and had this experience':'After Effectsを学び始めて体験したこと',
'Putting preset on adjustment layer':'調整レイヤーにプリセットを適用するとキーフレームがずれる',
'Tree (Procreate Dreams/ After effects)':'木のアニメーション制作：Procreate DreamsとAfter Effects',
'Help needed - Responsive MOGRT affecting graphics issue':'MOGRTの長さ変更でグラフィックに不具合が出る問題',
'Reviews and Comments Are Now Live on aescripts':'aescriptsでレビュー・コメント機能が公開',
'Judge/Roast my educational motion graphic video made in after effects':'After Effectsで作った教育向け動画への講評を募集',
'Ethics of Object Matte, does it use Gen AI?':'Object Matteは生成AIを使う？利用上の疑問',
'Not enough memory to alocate error but I have enough':'メモリに余裕があるのに「メモリ不足」エラーが出る',
'Documentary video animation. Playing around with old photos and scanned papers':'古い写真とスキャンした紙を使ったドキュメンタリー映像の表現',
'need help with looping VR Digital Glitch':'VR Digital Glitchを自然にループさせるには？',
'Rotation keyframes not following the keyframe path':'回転キーフレームが想定した動きにならない問題',
'How do I keep files in tact on After Effects when emailing them to someone':'After Effectsの素材を欠落させずに相手へ送るには？',
'US Mid-term results - data visualisation made entirely in AE using Atlas':'Atlasを使い、米中間選挙の結果をAfter Effectsで可視化',
"If you want to learn After Effects, here's a great place to start":'After Effectsをこれから学ぶ人向けの無料入門講座',
}
for article in data['articles']:
    for field in ('title', 'summary'):
        if article.get(field + '_ja'):
            continue
        original = article.get(field, '')
        if field == 'summary':
            original = re.sub(r'\s*submitted by\s.*', '', original, flags=re.I).strip(' .')
        article[field + '_original'] = original
        if not original:
            article[field + '_ja'] = '本文の抜粋がありません。元記事をご確認ください。'
        elif re.search(r'[ぁ-んァ-ン]', original):
            article[field + '_ja'] = original
        else:
            source = original
            for term, replacement in TERMS.items():
                source = re.sub(re.escape(term), replacement, source, flags=re.I)
            article[field + '_ja'] = TITLES.get(original) if field == 'title' else None
            if not article[field + '_ja']:
                article[field + '_ja'] = argostranslate.translate.translate(source, 'en', 'ja')
    article['translation'] = 'argos_machine_translation'
data['notice'] = '公式ニュース・RSSのタイトルと抜粋を日本語に自動翻訳しています。誤訳や省略があるため、詳細は原文をご確認ください。評価はキーワードによる自動判定です。'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print('Japanese translations:', len(data['articles']))
