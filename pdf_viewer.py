"""Visualiseur P&ID interactif côté navigateur : zoom/pan/rotation sans rerun Streamlit."""
import base64
import html
import io

import pymupdf
import streamlit as st
import streamlit.components.v1 as components


@st.cache_data(show_spinner=False, max_entries=12)
def render_page(pdf_data: bytes, page_number: int, max_edge: int = 2800) -> tuple[bytes, int, int]:
    """Une seule rasterisation par page; les gestes suivants sont faits par le navigateur."""
    with pymupdf.open(stream=pdf_data, filetype="pdf") as doc:
        page = doc[page_number]
        bounds = page.rect
        scale = min(max_edge / max(bounds.width, bounds.height), 3.0)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        return pix.tobytes("png"), pix.width, pix.height


def show_viewer(pdf_data: bytes, page_number: int, height: int = 590) -> None:
    image_data, width, img_height = render_page(pdf_data, page_number)
    b64 = base64.b64encode(image_data).decode("ascii")
    markup = r'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"/>
<style>
*{box-sizing:border-box}html,body{margin:0;height:100%;font-family:Inter,Segoe UI,Arial,sans-serif;overflow:hidden;background:#e9edf2}
#viewport{width:100%;height:100vh;position:relative;overflow:hidden;cursor:grab;touch-action:none;background-image:radial-gradient(#cad1db 0.8px,transparent 0.8px);background-size:20px 20px}
#viewport.drag{cursor:grabbing}#drawing{position:absolute;left:0;top:0;transform-origin:center center;max-width:none;user-select:none;-webkit-user-drag:none;box-shadow:0 8px 30px #18243824;background:#fff}
.toolbar{position:absolute;z-index:3;left:50%;top:12px;transform:translateX(-50%);display:flex;align-items:center;gap:3px;background:#fff;border:1px solid #d7dde5;border-radius:11px;padding:5px;box-shadow:0 3px 13px #1f293720;white-space:nowrap}
button{border:0;background:transparent;color:#273549;font-size:15px;height:32px;min-width:34px;border-radius:7px;cursor:pointer}button:hover{background:#edf3fc}button:focus-visible{outline:2px solid #2563eb}.separator{height:22px;width:1px;background:#dce2ea;margin:0 4px}.pct{min-width:48px;text-align:center;font-size:12px;font-weight:600;color:#344054}
.hint{position:absolute;bottom:10px;left:12px;font-size:11px;border:1px solid #dbe2eb;border-radius:6px;color:#556477;background:#fffffff0;padding:7px 9px;pointer-events:none}
@media(max-width:480px){.toolbar{top:8px}button{min-width:30px}.hint{font-size:10px}}
</style></head><body>
<div id="viewport" aria-label="Visualiseur du plan P&ID">
<img id="drawing" draggable="false" width="__WIDTH__" height="__HEIGHT__" src="data:image/png;base64,__IMAGE__" alt="Plan P&ID"/>
<div class="toolbar" aria-label="Outils d'affichage">
<button type="button" id="minus" title="Dézoomer">−</button><span class="pct" id="pct">100%</span><button type="button" id="plus" title="Zoomer">+</button>
<span class="separator"></span><button type="button" id="fit" title="Adapter à la fenêtre">⛶</button>
<button type="button" id="turn" title="Tourner de 90 degrés">↻</button>
<button type="button" id="reset" title="Remettre à zéro">⟲</button></div>
<div class="hint">Molette : zoom · Glisser : déplacer · Double-clic : adapter</div></div>
<script>
(()=>{
 const viewport=document.getElementById('viewport'),img=document.getElementById('drawing'),pct=document.getElementById('pct');
 const W=__WIDTH__,H=__HEIGHT__;let scale=1,angle=0,tx=0,ty=0,drag=false,lastX=0,lastY=0;
 function draw(){img.style.transform=`translate(${tx}px,${ty}px) translate(-50%,-50%) rotate(${angle}deg) scale(${scale})`;pct.textContent=Math.round(scale*100)+'%';}
 // Image positioned with center at viewport center plus tx/ty
 img.style.left='50%';img.style.top='50%';
 function fit(){const rotated=angle%180!==0;const a=rotated?H:W,b=rotated?W:H;scale=Math.min((viewport.clientWidth-28)/a,(viewport.clientHeight-28)/b,1);tx=0;ty=0;draw();}
 function zoom(factor,cx=viewport.clientWidth/2,cy=viewport.clientHeight/2){const next=Math.max(0.08,Math.min(scale*factor,8));const ratio=next/scale;
 tx=(tx-(cx-viewport.clientWidth/2))*ratio+(cx-viewport.clientWidth/2);
 ty=(ty-(cy-viewport.clientHeight/2))*ratio+(cy-viewport.clientHeight/2);scale=next;draw();}
 document.getElementById('minus').onclick=()=>zoom(1/1.3);
 document.getElementById('plus').onclick=()=>zoom(1.3);
 document.getElementById('fit').onclick=fit;
 document.getElementById('turn').onclick=()=>{angle=(angle+90)%360;fit();};
 document.getElementById('reset').onclick=()=>{angle=0;fit();};
 viewport.addEventListener('wheel',e=>{e.preventDefault();const box=viewport.getBoundingClientRect();zoom(e.deltaY<0?1.14:1/1.14,e.clientX-box.left,e.clientY-box.top);},{passive:false});
 viewport.addEventListener('pointerdown',e=>{if(e.target.closest('button'))return;drag=true;lastX=e.clientX;lastY=e.clientY;viewport.classList.add('drag');viewport.setPointerCapture(e.pointerId);});
 viewport.addEventListener('pointermove',e=>{if(!drag)return;tx+=e.clientX-lastX;ty+=e.clientY-lastY;lastX=e.clientX;lastY=e.clientY;draw();});
 function release(){drag=false;viewport.classList.remove('drag');}viewport.addEventListener('pointerup',release);viewport.addEventListener('pointercancel',release);
 viewport.addEventListener('dblclick',e=>{if(!e.target.closest('button'))fit();});
 window.addEventListener('resize',fit);img.onload=fit;if(img.complete)fit();
})();
</script></body></html>'''
    markup = markup.replace('__WIDTH__', str(width)).replace('__HEIGHT__', str(img_height)).replace('__IMAGE__', b64)
    components.html(markup, height=height, scrolling=False)
