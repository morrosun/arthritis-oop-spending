# -*- coding: utf-8 -*-
"""
36_export_figures.py — 从两份自包含 HTML 中抽取 5×2 个内嵌 SVG，导出期刊投稿三种格式：

  *.pdf  矢量分图 PDF（原 SVG → MuPDF convert_to_pdf；文字保留、字体嵌入，可选中/检索）
  *.tif  300 dpi TIFF（按目标印刷宽度 174 mm 双栏换算像素；RGB + LZW 无损；dpi 标记 300）
  *.eps  矢量 EPS（文字转路径 MuPDF get_svg_image(text_as_path=1) → svglib → renderPS；
                   零 findfont / 零 show，不依赖任何外部字体，中文亦为轮廓，可直接交印厂）
  *.svg  原始矢量源文件（便于后续微调）

另出：All_Figures_{EN,CN}.pdf（五图合订，便于审稿通读）
     figures_manifest.csv / figures_validation.txt（逐文件校验）

命名：OOPE_Fig{1..5}_{EN,CN}.{pdf,tif,eps,svg}
图题与图注见 方向A_Figures_{EN,CN}.html 与两份 IMRaD 初稿；本目录只放图版本体。
"""
import io, os, re, sys, time, csv
import fitz
from PIL import Image
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPS

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
DEST = os.path.join(ROOT, 'figures')
os.makedirs(DEST, exist_ok=True)
HTML = {'EN': os.path.join(ROOT, '方向A_Figures_EN.html'),
        'CN': os.path.join(ROOT, '方向A_Figures_CN.html')}
NAMES = {1: 'forest', 2: 'eventstudy', 3: 'components', 4: 'countries',
         5: 'ses_stratified'}
NFIG = len(NAMES)
TARGET_WIDTH_MM = 174.0     # 期刊双栏常见成品宽度
DPI = 300
LOG = []
def log(s=''):
    print(s, flush=True); LOG.append(str(s))

def svg_dims(s):
    m = re.search(r'<svg[^>]*viewBox="0 0 ([\d.]+) ([\d.]+)"', s)
    return (float(m.group(1)), float(m.group(2))) if m else (1000., 700.)

def eps_validate(path):
    b = open(path, 'rb').read(); t = b.decode('latin-1')
    head = t[:40]
    bb = re.search(r'%%BoundingBox:\s*([^\n]+)', t)
    return dict(bytes=len(b), header_ok=head.startswith('%!PS-Adobe-3.0 EPSF-3.0'),
                bbox=bb.group(1).strip() if bb else '',
                findfont=len(re.findall(r'findfont', t)),
                show=len(re.findall(r'\)\s+show', t)),
                eof='%%EOF' in t[-200:], showpage='showpage' in t)

def main():
    log('论文级图形导出 | ' + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('目标宽度 %.0f mm / %d dpi；PDF 保留文字并嵌入字体；EPS 文字转路径（零字体依赖）' % (TARGET_WIDTH_MM, DPI))
    log('输出目录：' + DEST + '\n')
    rows = []
    for lang, hp in HTML.items():
        src = open(hp, encoding='utf-8').read()
        svgs = re.findall(r'<svg .*?</svg>', src, re.S)
        assert len(svgs) == NFIG, '%s: expected %d SVG, got %d' % (lang, NFIG, len(svgs))
        combo = []
        for i, s in enumerate(svgs, 1):
            stem = 'OOPE_Fig%d_%s' % (i, lang)
            w, h = svg_dims(s)
            svg_path = os.path.join(DEST, stem + '.svg')
            open(svg_path, 'w', encoding='utf-8').write(s)

            # ---- PDF（矢量，保留文字，字体嵌入）----
            d = fitz.open(svg_path)
            pdf_bytes = d.convert_to_pdf()
            pdf_path = os.path.join(DEST, stem + '.pdf')
            open(pdf_path, 'wb').write(pdf_bytes)
            pdoc = fitz.open(stream=pdf_bytes, filetype='pdf')
            fonts = [f[3] for f in pdoc[0].get_fonts()]
            combo.append(pdf_bytes)
            d.close()

            # ---- TIFF（300 dpi，LZW）----
            target_px = int(round(TARGET_WIDTH_MM / 25.4 * DPI))
            scale = target_px / w
            pix = pdoc[0].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            tif_path = os.path.join(DEST, stem + '.tif')
            img.save(tif_path, format='TIFF', dpi=(DPI, DPI), compression='tiff_lzw')
            im2 = Image.open(tif_path)
            tags = im2.tag_v2
            xres = tags.get(282); yres = tags.get(283); unit = tags.get(296)
            tif_info = dict(px=(im2.size[0], im2.size[1]), mode=im2.mode,
                            dpi_x=float(xres) if xres else None,
                            dpi_y=float(yres) if yres else None,
                            unit=unit, compression=str(im2.info.get('compression')),
                            bytes=os.path.getsize(tif_path))
            im2.close()
            pdoc.close()

            # ---- EPS（文字转路径 → 无字体依赖）----
            d3 = fitz.open(svg_path)
            path_svg = d3[0].get_svg_image(text_as_path=1)
            ps_path = os.path.join(DEST, stem + '_paths.svg')
            open(ps_path, 'w', encoding='utf-8').write(path_svg)
            dr = svg2rlg(ps_path)
            eps_path = os.path.join(DEST, stem + '.eps')
            renderPS.drawToFile(dr, eps_path, fmt='EPS')
            # reportlab renderPS 不写 DSC 结束标记；按 EPSF-3.0 规范补齐 %%EOF
            with open(eps_path, 'rb') as ef:
                tail = ef.read()[-200:]
            if b'%%EOF' not in tail:
                with open(eps_path, 'ab') as ef:
                    ef.write(b'\n%%EOF\n')
            ev = eps_validate(eps_path)
            d3.close()

            log('%s Fig%d (%-11s) 原尺寸 %.0f×%.0f → TIFF %d×%d px @%d dpi | PDF %d KB (%d fonts) | EPS %d KB (findfont=%d)' % (
                lang, i, NAMES[i], w, h, tif_info['px'][0], tif_info['px'][1], DPI,
                len(pdf_bytes)//1024, len(fonts), ev['bytes']//1024, ev['findfont']))
            rows.append(dict(lang=lang, fig=i, name=NAMES[i], stem=stem,
                             svg_w=w, svg_h=h,
                             pdf_bytes=len(pdf_bytes), pdf_fonts=';'.join(fonts),
                             tif_px_w=tif_info['px'][0], tif_px_h=tif_info['px'][1],
                             tif_dpi_x=tif_info['dpi_x'], tif_dpi_y=tif_info['dpi_y'],
                             tif_unit=tif_info['unit'], tif_mode=tif_info['mode'],
                             tif_compression=tif_info['compression'], tif_bytes=tif_info['bytes'],
                             eps_bytes=ev['bytes'], eps_header_ok=ev['header_ok'],
                             eps_bbox=ev['bbox'], eps_findfont=ev['findfont'],
                             eps_show=ev['show'], eps_eof=ev['eof'], eps_showpage=ev['showpage']))
        # 合订 PDF
        allp = os.path.join(DEST, 'All_Figures_%s.pdf' % lang)
        doc = fitz.open()
        for b in combo:
            x = fitz.open(stream=b, filetype='pdf')
            doc.insert_pdf(x); x.close()
        doc.save(allp); doc.close()
        log('%s 合订 PDF -> %s (%d 页)\n' % (lang, os.path.basename(allp), NFIG))

    with open(os.path.join(DEST, 'figures_manifest.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys())); wr.writeheader(); wr.writerows(rows)

    # ---- 校验 ----
    log('=== 校验 ===')
    ok = True
    for r in rows:
        chk = [
            ('PDF 存在且 >10KB', r['pdf_bytes'] > 10000),
            ('TIFF 宽度按 174mm@300dpi 换算', abs(r['tif_px_w'] - round(TARGET_WIDTH_MM/25.4*DPI)) <= 1),
            ('TIFF dpi 标记 = 300', r['tif_dpi_x'] == 300 and r['tif_dpi_y'] == 300),
            ('TIFF 为 RGB + LZW', r['tif_mode'] == 'RGB' and 'lzw' in r['tif_compression'].lower()),
            ('EPS 头合法', r['eps_header_ok']),
            ('EPS 无字体依赖', r['eps_findfont'] == 0 and r['eps_show'] == 0),
            ('EPS 结构完整', r['eps_eof'] and r['eps_showpage'] and bool(r['eps_bbox'])),
        ]
        bad = [n for n, v in chk if not v]
        if bad: ok = False
        log('  %-22s %s' % (r['stem'], 'PASS' if not bad else 'FAIL: ' + ', '.join(bad)))
    log('\n合计：%d 张图 × 4 格式 = %d 个文件 + 2 本合订 PDF + manifest' % (len(rows), len(rows)*4))
    log('最终判定：%s' % ('ALL PASS' if ok else 'HAS FAILURES'))
    open(os.path.join(DEST, 'figures_validation.txt'), 'w', encoding='utf-8').write('\n'.join(LOG))

if __name__ == '__main__':
    main()
