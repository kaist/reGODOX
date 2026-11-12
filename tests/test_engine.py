from pathlib import Path
import hashlib
import pytest
from PIL import Image
from regodox import engine
from regodox.images import crop_image,indexed_image,load_image


def test_exact_complete_build(profile,original):
    patched,report=engine.build(original)
    assert hashlib.sha256(patched).hexdigest()==profile.default_sha256
    assert engine.identify(patched)==(profile,'regodox')
    assert patched[engine.PROTECTED_OFFSET:]==original[engine.PROTECTED_OFFSET:]
    assert report['all_patches_applied'] and report['CamLCD_menu']==profile.camlcd_menu
    assert engine.build(patched)[0]==patched


def test_custom_splash_preserves_code(profile,original):
    base,_=engine.build(original)
    art=Image.new('RGB',(789,201),'#9258db')
    image=indexed_image(crop_image(art,(0,0),2),True)
    patched,_=engine.build(original,image)
    lo=profile.pixel_offset;hi=lo+engine.PAYLOAD_SIZE
    assert patched[:lo]==base[:lo] and patched[hi:]==base[hi:]
    assert engine.identify(patched)==(profile,'regodox')
    assert engine.decode_splash(patched[lo:hi]).convert('RGB').tobytes()==image.convert('RGB').tobytes()
    assert engine.build(patched,image)[0]==patched


def test_unknown_code_is_rejected(profile,original):
    data=bytearray(original);data[100]^=1
    with pytest.raises(ValueError):engine.build(bytes(data))
    patched,_=engine.build(original);data=bytearray(patched);data[100]^=1
    with pytest.raises(ValueError):engine.identify(bytes(data))
    with pytest.raises(ValueError):engine.build(original[:-1])


def test_atomic_save_does_not_overwrite_input(tmp_path,profile,original):
    source=tmp_path/profile.original_name;source.write_bytes(original)
    patched,_=engine.build(original)
    with pytest.raises(ValueError):engine.save_atomic(source,patched,source)
    dest=tmp_path/profile.output_name;engine.save_atomic(dest,patched,source)
    assert dest.read_bytes()==patched and source.read_bytes()==original
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('size',[(1,1),(20,900),(900,20),(368,448)])
@pytest.mark.parametrize('dither',[False,True])
def test_crop_and_palette(size,dither):
    image=Image.new('RGB',size,'#fe8056')
    result=indexed_image(crop_image(image,(-100,10000),5),dither)
    assert result.size==(368,448) and max(result.tobytes())<4
    assert len(result.getcolors())<=4
    assert engine.decode_splash(engine.encode_splash(result)).convert('RGB').tobytes()==result.convert('RGB').tobytes()


def test_transparency_and_orientation(tmp_path):
    p=tmp_path/'transparent.png';Image.new('RGBA',(20,10),(255,0,0,0)).save(p)
    assert load_image(p).getpixel((0,0))==(0,0,0)
    p=tmp_path/'orientation.jpg';im=Image.new('RGB',(40,20),'red');exif=im.getexif();exif[274]=6
    im.save(p,exif=exif)
    assert load_image(p).size==(20,40)


def test_default_artwork():
    image=engine.default_splash()
    assert len(image.getcolors())==4 and image.size==(368,448)
    assert engine.encode_splash(image)==engine.resource('default-splash.bin').read_bytes()
