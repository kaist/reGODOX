"""Scriptable access to the same backend used by Firmware Studio."""
import argparse
import hashlib
import json
from pathlib import Path
from .engine import build,identify,profiles,save_atomic
from .images import load_image,crop_image,indexed_image


def main():
    parser=argparse.ArgumentParser(prog='regodox',description='Patch supported Godox X3 firmware.')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('profiles',help='List supported original versions')
    inspect=sub.add_parser('inspect');inspect.add_argument('firmware',type=Path)
    patch=sub.add_parser('patch');patch.add_argument('firmware',type=Path)
    patch.add_argument('-o','--output',required=True,type=Path)
    patch.add_argument('--splash',type=Path,help='Center-crop and quantize this image; use GUI for custom crop')
    patch.add_argument('--dither',action='store_true')
    all_=sub.add_parser('build-all');all_.add_argument('--input-dir',type=Path,default=Path('firmware/original'))
    all_.add_argument('--output-dir',type=Path,default=Path('dist/firmware'))
    args=parser.parse_args()
    try:
        if args.command=='profiles':
            for p in profiles():print(p.id,p.brand,p.version,p.original_name)
        elif args.command=='inspect':
            p,kind=identify(args.firmware.read_bytes())
            print(json.dumps({'model':p.id,'brand':p.brand,'version':p.version,'kind':kind,
                'CamLCD_menu':p.camlcd_menu,'camera_parameters':p.camera_parameters},indent=2))
        elif args.command=='patch':
            splash=None
            if args.splash:
                image=load_image(args.splash)
                splash=indexed_image(crop_image(image,(image.width/2,image.height/2),1),args.dither)
            data,report=build(args.firmware.read_bytes(),splash)
            save_atomic(args.output,data,args.firmware)
            print(json.dumps(report,indent=2))
        elif args.command=='build-all':
            args.output_dir.mkdir(exist_ok=True,parents=True);reports=[];sums=[]
            for p in profiles():
                source=args.input_dir/p.original_name
                data,report=build(source.read_bytes())
                save_atomic(args.output_dir/p.output_name,data,source)
                (args.output_dir/(p.output_name+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
                sums.append(hashlib.sha256(data).hexdigest()+'  '+p.output_name);reports.append(report)
                print(p.output_name,report['output_sha256'])
            (args.output_dir/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='ascii')
            (args.output_dir/'build-report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    except (OSError,ValueError) as exc:
        parser.exit(2,str(exc)+'\n')


if __name__=='__main__':main()
