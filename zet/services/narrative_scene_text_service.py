"""Assembly lettering drafts and immutable confirmed revisions."""
import base64
import hashlib
import math
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from PIL import Image
from zet.services.scene_text_style_service import effective_style, signature
from zet.services.scene_text_render_service import render, Runs
from zet.services.atomic_file_service import write_bytes_atomic

class NarrativeSceneTextService:
    def __init__(self, author): self.author=author; self.repository=author.repository
    def state(self, story, scene, target, candidate=None):
        record=self.repository.read(story,scene,target)
        if record['kind']!='assembly': raise ValueError('Scene text belongs to final assemblies.')
        entries=record.get('scene_text',[])
        placements=deepcopy({e['id']: e.get('placement',{}) for e in entries})
        source=None
        if candidate:
            item=record['candidates'][candidate]
            seed=item.get('assembly_snapshot',{}).get('scene_text_seed',{})
            placements.update(seed);placements.update(item.get('scene_text_placements',{}))
            source=self.repository.folder(story,scene,target)/item['image']
        placements={e['id']:placements.get(e['id'],{}) for e in entries}
        style=effective_style(self.repository.library_root,self.repository.read(story))
        token=signature([entries,placements,style,hashlib.sha256(source.read_bytes()).hexdigest() if source else None])
        return dict(entries=entries,placements=placements,style=style,revision=record.get('scene_text_revision',0),token=token,locked=bool(candidate and record['candidates'][candidate].get('locked')))
    def save(self, story,scene,target,data,candidate=None):
        with self.repository.lock():
            state=self.state(story,scene,target,candidate)
            if data.get('revision')!=state['revision']: raise ValueError('Scene text changed. Reload before saving.')
            record=self.repository.read(story,scene,target)
            if candidate and record['candidates'][candidate].get('locked'): raise ValueError('Unlock this image before editing scene text.')
            if candidate:
                record['candidates'][candidate]['scene_text_placements']=data['placements']
            if not candidate or 'entries' in data:
                entries=data['entries']
                if not isinstance(entries,list) or len(entries)>64: raise ValueError('Choose up to 64 text entries.')
                ids=set()
                for e in entries:
                    if set(e)-{'id','text','tail','placement'} or not isinstance(e.get('id'),str) or e['id'] in ids or len(e['id'])>80: raise ValueError('Invalid text entry identity.')
                    ids.add(e['id'])
                    if not isinstance(e.get('text'),str) or len(e['text'])>10000 or e.get('tail') not in {'none','straight'}: raise ValueError('Invalid text entry.')
                    Runs(e['text'])
                record['scene_text']=entries
            placements = record['candidates'][candidate].get('scene_text_placements',{}) if candidate else {e['id']:e.get('placement',{}) for e in record['scene_text']}
            if not isinstance(placements,dict) or set(placements)-{e['id'] for e in record.get('scene_text',[])}: raise ValueError('Invalid placement entries.')
            for place in placements.values():
                if not isinstance(place,dict) or set(place)-{'box','tip','attachment'}: raise ValueError('Invalid placement fields.')
                for key,value in place.items():
                    values=[value] if key=='attachment' else value
                    if not isinstance(values,list) or len(values)!={'box':4,'tip':2,'attachment':1}[key] or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in values): raise ValueError('Invalid placement coordinates.')
            record['scene_text_revision']=state['revision']+1
            self.repository.write(record,story,scene,target)
            return self.state(story,scene,target,candidate)
    def preview(self,story,scene,target,data,candidate=None):
        state=self.state(story,scene,target,candidate)
        record=self.repository.read(story,scene,target)
        size=(record['width'],record['height'])
        if candidate:
            with Image.open(self.repository.folder(story,scene,target)/record['candidates'][candidate]['image']) as source: size=source.size
        overlay,errors=render(size,data.get('entries',state['entries']),data.get('placements',state['placements']),state['style'])
        output=BytesIO();overlay.save(output,format='PNG')
        return {**state,'overlay':'data:image/png;base64,'+base64.b64encode(output.getvalue()).decode(),'errors':errors}
    def confirm(self,story,scene,target,candidate,data):
        with self.repository.lock():
            state=self.state(story,scene,target,candidate)
            if state['token']!=data.get('token'): raise ValueError('Text, style or image changed. Preview again before confirming.')
            record=self.repository.read(story,scene,target); item=record['candidates'][candidate]
            if item.get('locked'): raise ValueError('Unlock this image before replacing scene text.')
            root=self.repository.folder(story,scene,target)
            with Image.open(root/item['image']) as source: artwork=source.convert('RGBA')
            overlay,errors=render(artwork.size,state['entries'],state['placements'],state['style'])
            if errors: raise ValueError('; '.join(e['message'] for e in errors))
            artwork.alpha_composite(overlay); output=BytesIO();artwork.save(output,format='PNG')
            relative=f'lettering/{candidate}/{uuid4().hex}.png'
            write_bytes_atomic(root/relative,output.getvalue())
            item['scene_text_final']={**state,'image':relative}
            record['selected_id']=candidate
            self.repository.write(record,story,scene,target)
            return self.author.target(story,scene,target)

def finished_path(repository,story,scene,target,candidate):
    record=repository.read(story,scene,target); item=record['candidates'][candidate]
    path=repository.folder(story,scene,target)/item.get('scene_text_final',{}).get('image',item['image'])
    if not path.resolve().is_relative_to(repository.folder(story,scene,target).resolve()): raise ValueError('Invalid finished image path.')
    if not path.is_file(): raise FileNotFoundError('Confirmed scene image is unavailable.')
    return path
