"""Image loading, fixed-aspect cropping and adaptive four-color quantization."""
from pathlib import Path
from PIL import Image,ImageOps
from .engine import WIDTH,HEIGHT


def load_image(path: str | Path) -> Image.Image:
    with Image.open(path) as opened:
        rgba=ImageOps.exif_transpose(opened).convert('RGBA')
        background=Image.new('RGBA',rgba.size,(0,0,0,255))
        background.alpha_composite(rgba)
        return background.convert('RGB')


def crop_image(image: Image.Image, center: tuple[float,float], zoom: float) -> Image.Image:
    iw,ih=image.size;scale=max(WIDTH/iw,HEIGHT/ih)*max(1,zoom)
    cw,ch=WIDTH/scale,HEIGHT/scale
    cx=min(max(center[0],cw/2),iw-cw/2);cy=min(max(center[1],ch/2),ih-ch/2)
    return image.resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS,box=(cx-cw/2,cy-ch/2,cx+cw/2,cy+ch/2))


def indexed_image(image: Image.Image,dither: bool=False) -> Image.Image:
    rgb=image.convert('RGB');adaptive=rgb.quantize(colors=4,method=Image.Quantize.FASTOCTREE)
    palette=adaptive.getpalette()[:12];used=len(adaptive.getcolors())
    colors=[tuple(palette[i*3:i*3+3]) for i in range(used)]
    colors+=[colors[-1]]*(4-used)
    p=Image.new('P',(1,1));p.putpalette([v for c in colors for v in c]*64)
    q=rgb.quantize(palette=p,dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE)
    lookup=bytes(next(j for j in range(4) if colors[j]==colors[i%4]) for i in range(256))
    result=Image.frombytes('P',q.size,q.tobytes().translate(lookup))
    result.putpalette([v for c in colors for v in c]+[0]*756)
    return result
