"""Deck Card Widget: dual-side object positions/visibility and QR canvas geometry.

Additive upgrade. Keeps legacy top-level fields as a projection of whichever
side the editor currently displays; stores authoritative per-side state in
layer['data_sides']. Neither card IDs nor DMS bridge APIs are changed.
"""
from __future__ import annotations
import copy
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont

SIDES = ('full-data', 'qr-data')
GEOMETRY_KEYS = ('x','y','size','scale','opacity','rotation','flip_x','flip_y','z','wrap_width','visible')
FRAME_DEFAULTS = {'frame': (14,14,946,486), 'three_rows': (52,86,314,207),
                  'logo': (52,229,302,464), 'qr': (345,92,360),
                  'info': (732,92,913,229), 'sponsor': (732,245,913,464)}
TEXT_DEFAULTS = {'right_brand': (905,127), 'right_subtitle': (905,150),
                 'activity_label': (905,191), 'host_label': (905,213)}

def fresh_side(layer):
    return {k:copy.deepcopy(layer[k]) for k in GEOMETRY_KEYS if k in layer}

def ensure_layer(layer):
    if not isinstance(layer, dict) or layer.get('type') not in {'emoji','image','text'}:
        return layer
    sides=layer.get('data_sides')
    if not isinstance(sides,dict):
        base=fresh_side(layer)
        sides={'full-data':copy.deepcopy(base), 'qr-data':copy.deepcopy(base)}
        layer['data_sides']=sides
    for side in SIDES:
        if not isinstance(sides.get(side),dict):
            sides[side]=copy.deepcopy(sides.get('full-data',fresh_side(layer)))
        sides[side].setdefault('visible',layer.get('visible',True))
    if layer.get('only_side') not in (*SIDES, None):
        layer['only_side']=None
    return layer

def ensure_card(card):
    for layer in card.get('layers',[]):
        ensure_layer(layer)
    return card

def side_snapshot(card, side):
    for layer in card.get('layers',[]):
        ensure_layer(layer)
        if 'data_sides' in layer:
            layer['data_sides'][side].update(fresh_side(layer))

def side_apply(card, side):
    for layer in card.get('layers',[]):
        ensure_layer(layer)
        state=layer.get('data_sides',{}).get(side,{})
        for key,value in state.items():
            if key in GEOMETRY_KEYS: layer[key]=copy.deepcopy(value)
        only=layer.get('only_side')
        if only in SIDES and only != side:
            layer['visible']=False

def default_qr_layout():
    return {'rects':{k:list(v) for k,v in FRAME_DEFAULTS.items()},
            'texts':{k:list(v) for k,v in TEXT_DEFAULTS.items()}}

def ensure_layout(data):
    head=data.setdefault('header',{})
    cfg=head.setdefault('qr_data_layout',default_qr_layout())
    if not isinstance(cfg,dict): cfg=default_qr_layout();head['qr_data_layout']=cfg
    rects=cfg.setdefault('rects',{})
    texts=cfg.setdefault('texts',{})
    for k,v in FRAME_DEFAULTS.items():
        if not isinstance(rects.get(k),list) or len(rects[k])!=len(v): rects[k]=list(v)
    for k,v in TEXT_DEFAULTS.items():
        if not isinstance(texts.get(k),list) or len(texts[k])!=2: texts[k]=list(v)
    return cfg

def install(cls):
    original_init=cls.__init__
    original_draw=cls.redraw_output
    original_load=cls.load_active_card_into_editor
    original_select=cls.select_card
    original_effective=cls.effective_display_mode
    original_toggle=cls.toggle_live_qr_data
    original_set=cls.set_live_qr_data
    original_draw_text=cls.draw_display_text
    original_draw_qr=cls.draw_qr_data

    def init(self,*a,**kw):
        self._dualside_active={}
        self._dualside_preview=None
        self._dualside_ui_built=False
        original_init(self,*a,**kw)
        ensure_layout(self.store.data)
        self._dualside_ui_built=True
        self.dualside_refresh_ui()

    def qr_data_layout(self):
        cfg=ensure_layout(self.store.data)
        result={}
        for key,defaults in FRAME_DEFAULTS.items():
            try: raw=[int(v) for v in cfg['rects'][key]]
            except (ValueError,TypeError): raw=list(defaults)
            if key=='qr':
                x,y,size=raw
                size=max(80,min(440,size))
                result[key]=(max(0,min(960-size,x)),max(0,min(500-size,y)),size)
            else:
                x1,y1,x2,y2=raw
                x1=max(0,min(958,x1));y1=max(0,min(498,y1))
                x2=max(x1+2,min(960,x2));y2=max(y1+2,min(500,y2))
                result[key]=(x1,y1,x2,y2)
        return result

    def qr_data_text_position(self,key):
        return tuple(ensure_layout(self.store.data)['texts'].get(key, TEXT_DEFAULTS[key]))

    def ui_selected_layer(self,typ):
        return {'emoji':self.selected_sticker, 'image':self.selected_image_layer,
                'text':self.selected_text_layer}[typ]()

    def dualside_sync(self):
        card=self.store.active_card()
        ensure_card(card)
        old=self._dualside_active.get(id(card))
        new=self.effective_display_mode(card)
        if old in SIDES: side_snapshot(card,old)
        # Project from authoritative per-side state even without a mode change.
        # This enforces ONLY flags when an existing Show button is clicked on
        # an ineligible side without corrupting the eligible side.
        side_apply(card,new)
        if old!=new:
            self._dualside_active[id(card)]=new
            self.dualside_reload_selected_controls()
        self.dualside_refresh_ui()
        return new

    def redraw(self):
        if hasattr(self,'store') and hasattr(self,'live_qr_data_var'):
            self.dualside_sync()
        return original_draw(self)

    def load_editor(self):
        if hasattr(self,'store') and hasattr(self,'live_qr_data_var'):
            self.dualside_sync()
        result=original_load(self)
        self.dualside_refresh_ui()
        return result

    def select_card(self,card_id):
        self.dualside_sync()
        self._dualside_preview=None
        return original_select(self,card_id)

    def effective(self,card):
        if self._dualside_preview and self._dualside_preview[0] == id(card):
            return self._dualside_preview[1]
        return original_effective(self,card)

    def set_live(self,enabled):
        self._dualside_preview=None  # Remote DMS requests remain authoritative.
        return original_set(self,enabled)

    def toggle(self):
        target=not bool(self.live_qr_data_var.get())
        original_set(self,target)
        # Only the *manual* controller click can temporarily preview Full
        # on a card whose saved default is QR; do not mutate per-card setting.
        card=self.store.active_card()
        if not target and card.get('display_mode')=='qr-data':
            self._dualside_preview=(id(card),'full-data')
        else:
            self._dualside_preview=None
        self.redraw_output()
        self.update_live_qr_data_button()

    def refresh_ui(self):
        if not getattr(self,'_dualside_ui_built',False): return
        for typ,vars in getattr(self,'_dualside_scope_vars',{}).items():
            layer=self.ui_selected_layer(typ)
            val=layer.get('only_side') if layer else None
            vars['full-data'].set(val=='full-data')
            vars['qr-data'].set(val=='qr-data')
        if hasattr(self,'dualside_status_var'):
            card=self.store.active_card()
            self.dualside_status_var.set('Editing: '+self.effective_display_mode(card).upper()+
                ' | sticker positions & visibility are saved separately')

    def reload_selected(self):
        # Those editor widgets represent the currently projected layer fields.
        if not getattr(self,'_dualside_ui_built',False):return
        for fn in (self.load_selected_sticker_into_controls,
                   self.load_selected_image_into_controls,
                   self.load_selected_text_layer_into_controls):
            try: fn()
            except (AttributeError,tk.TclError): pass

    def toggle_scope(self,typ,side):
        layer=self.ui_selected_layer(typ)
        if not layer:return
        ensure_layer(layer)
        current=self.effective_display_mode(self.store.active_card())
        side_snapshot(self.store.active_card(),current)
        new=None if layer.get('only_side')==side else side
        layer['only_side']=new
        if new:
            layer['data_sides'][new]['visible']=True
            layer['data_sides'][next(s for s in SIDES if s!=new)]['visible']=False
        else:
            # Removing ONLY makes both sides eligible again, but preserves their
            # previous independent positions; Show/Hide remains per-side.
            for s in SIDES:layer['data_sides'][s]['visible']=True
        side_apply(self.store.active_card(),current)
        self.store.mark_dirty('layer-only-side-changed')
        self.dualside_refresh_ui()
        self.redraw_output()
        self.schedule_autosave()

    def setup_qr_tab_scroll(self,outer,inner):
        """Vertical-only scroll for QR Group and its global QR-Data geometry.

        Routed mouse wheel only when the pointer is over this tab; no timers,
        global scroll capture, or horizontal movement.
        """
        canvas=tk.Canvas(outer,highlightthickness=0,bd=0,yscrollincrement=18)
        scroll=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left',fill='both',expand=True)
        scroll.pack(side='right',fill='y')
        window=canvas.create_window((0,0),window=inner,anchor='nw')
        inner.bind('<Configure>',lambda _e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        def wheel(event):
            try:
                x=event.x_root-canvas.winfo_rootx();y=event.y_root-canvas.winfo_rooty()
                if not (0<=x<canvas.winfo_width() and 0<=y<canvas.winfo_height()):return
                units=(-1 if event.num==4 else 1) if getattr(event,'num',None) in (4,5) else -1 if event.delta>0 else 1
                canvas.yview_scroll(units*3,'units')
                return 'break'
            except (AttributeError,tk.TclError):pass
        for tag in ('<MouseWheel>','<Button-4>','<Button-5>'):
            self.root.bind_all(tag,wheel,add='+')

    def gui_setup(self,sticker_frame,image_frame,text_frame,qr_frame):
        self._dualside_scope_vars={}
        for typ,parent,row,colspan in [('emoji',sticker_frame,10,4),('image',image_frame,10,8),('text',text_frame,9,6)]:
            panel=ttk.LabelFrame(parent,text='Object side visibility',padding=4)
            panel.grid(row=row,column=0,columnspan=colspan,sticky='w',pady=(6,0))
            vars={s:tk.BooleanVar(value=False) for s in SIDES}
            self._dualside_scope_vars[typ]=vars
            ttk.Checkbutton(panel,text='Full-Data ONLY',variable=vars['full-data'],
                            command=lambda t=typ:self.dualside_toggle_scope(t,'full-data')).pack(side='left',padx=5)
            ttk.Checkbutton(panel,text='QR-Data ONLY',variable=vars['qr-data'],
                            command=lambda t=typ:self.dualside_toggle_scope(t,'qr-data')).pack(side='left',padx=5)
            ttk.Label(panel,text='Neither = both. Show/Hide applies to current side.').pack(side='left',padx=8)
        # Existing QR Group geometry is the small FULL-DATA QR. The independent
        # settings below belong ONLY to the large QR-DATA view, shared by cards.
        frame=ttk.LabelFrame(qr_frame,text='QR-Data global layout · all cards',padding=5)
        frame.grid(row=7,column=0,columnspan=8,sticky='ew',pady=(7,0))
        self._qr_layout_vars={}
        descriptions=[('frame','Outer frame'),('three_rows','Top three lanes'),
            ('logo','Logo bay'),('qr','Large QR + fallback'),
            ('info','Card data bay'),('sponsor','Sponsor bay')]
        cfg=ensure_layout(self.store.data)
        for ci,header in enumerate(('Area','X / left','Y / top','Right / size','Bottom')):
            ttk.Label(frame,text=header).grid(row=0,column=ci,sticky='w',padx=2)
        for row,(key,desc) in enumerate(descriptions,start=1):
            ttk.Label(frame,text=desc,width=22).grid(row=row,column=0,sticky='w',pady=1)
            values=cfg['rects'][key]
            for col,val in enumerate(values):
                v=tk.IntVar(value=int(val));self._qr_layout_vars[(key,col)]=v
                ttk.Spinbox(frame,from_=0,to=960 if col%2==0 else 500,width=6,
                    textvariable=v,command=self.apply_qr_data_layout).grid(row=row,column=col+1,sticky='w',padx=2)
        sep=len(descriptions)+1
        ttk.Label(frame,text='QR right-side text X / Y',font=('TkDefaultFont',9,'bold')).grid(row=sep,column=0,columnspan=4,sticky='w',pady=(7,2))
        for n,(key,desc) in enumerate([('right_brand','Widget name'),('right_subtitle','Widget subtitle'),
                                      ('activity_label','Link status'),('host_label','QR link location')],start=sep+1):
            ttk.Label(frame,text=desc,width=22).grid(row=n,column=0,sticky='w',pady=1)
            for idx,val in enumerate(cfg['texts'][key]):
                v=tk.IntVar(value=int(val));self._qr_layout_vars[('text:'+key,idx)]=v
                ttk.Spinbox(frame,from_=0,to=960 if idx==0 else 500,width=7,
                    textvariable=v,command=self.apply_qr_data_layout).grid(row=n,column=idx+1,sticky='w',padx=3)
        note_row=sep+6
        ttk.Button(frame,text='Apply to ALL QR-Data cards',command=self.apply_qr_data_layout).grid(row=note_row,column=0,columnspan=2,sticky='w',pady=(6,0))
        ttk.Button(frame,text='Reset QR layout',command=self.reset_qr_data_layout).grid(row=note_row,column=2,columnspan=3,sticky='w',pady=(6,0))
        self.dualside_status_var=tk.StringVar(value='Editing: FULL-DATA')
        ttk.Label(frame,textvariable=self.dualside_status_var).grid(row=note_row+1,column=0,columnspan=5,sticky='w')
        self._dualside_ui_built=True
        self.dualside_refresh_ui()

    def apply_qr_layout(self):
        cfg=ensure_layout(self.store.data)
        try:
            for (key,index),var in self._qr_layout_vars.items():
                arr=cfg['texts'][key[5:]] if key.startswith('text:') else cfg['rects'][key]
                arr[index]=int(var.get())
        except (ValueError,tk.TclError):return
        self.store.mark_dirty('qr-data-global-layout')
        self.redraw_output()
        self.schedule_autosave()

    def reset_qr_layout(self):
        self.store.data['header']['qr_data_layout']=default_qr_layout()
        cfg=ensure_layout(self.store.data)
        for (key,i),var in self._qr_layout_vars.items():
            arr=cfg['texts'][key[5:]] if key.startswith('text:') else cfg['rects'][key]
            var.set(arr[i])
        self.apply_qr_data_layout()

    def draw_qr_data(self,card):
        self._drawing_qr_data=True
        try:return original_draw_qr(self,card)
        finally:self._drawing_qr_data=False

    def draw_display_text(self, canvas, object_id, runtime_vars=None, override_text=None, override_x=None, override_y=None):
        if getattr(self,'_drawing_qr_data',False) and object_id in TEXT_DEFAULTS:
            pos=self.qr_data_text_position(object_id)
            if override_x is None:override_x=pos[0]
            if override_y is None:override_y=pos[1]
            obj=self.display_text_object_by_id(object_id)
            if obj:
                text=self.display_text_render_value(obj,runtime_vars,override_text)
                if object_id=='host_label':
                    # QR-only: show the location, not the 'QR LOC:' label.
                    for prefix in ('QR LOC:', 'SOURCE:', 'LOCATION:'):
                        if text.upper().startswith(prefix):text=text[len(prefix):].strip();break
                region=self.qr_data_layout()['info']
                width=max(14,region[2]-region[0]-14)
                font=tkfont.Font(root=self.root,font=self.display_text_font_tuple(obj))
                # Silent right overflow: no ellipsis on the info/link side.
                while text and font.measure(text)>width:text=text[:-1]
                override_text=text;runtime_vars=None
        return original_draw_text(self,canvas,object_id,runtime_vars,override_text,override_x,override_y)

    def delete_from_side(self,typ,original):
        layer=self.ui_selected_layer(typ)
        if layer is None:return
        ensure_layer(layer)
        side=self.effective_display_mode(self.store.active_card())
        side_snapshot(self.store.active_card(),side)
        only=layer.get('only_side')
        if only is None:
            other=next(s for s in SIDES if s!=side)
            if not messagebox.askyesno('Delete on both data sides?',
                         'Delete this object from '+other+' as well?\n\n'
                         'Yes = delete on BOTH sides.\nNo = hide only on '+side+' and keep it on '+other+'.',
                         parent=self.root):
                layer['only_side']=other
                layer['data_sides'][side]['visible']=False
                side_apply(self.store.active_card(),side)
                self.store.mark_dirty('hide-current-side-on-delete')
                self.dualside_refresh_ui();self.redraw_output();self.schedule_autosave()
                return
        # A one-side-only object can be removed outright from that side.
        return original(self)

    # Patching preserves the historical method names used by command callbacks.
    cls.__init__=init
    cls.qr_data_layout=qr_data_layout
    cls.qr_data_text_position=qr_data_text_position
    cls.ui_selected_layer=ui_selected_layer
    cls.dualside_sync=dualside_sync
    cls.dualside_refresh_ui=refresh_ui
    cls.dualside_reload_selected_controls=reload_selected
    cls.dualside_toggle_scope=toggle_scope
    cls.setup_dualside_controls=gui_setup
    cls.setup_qr_tab_scroll=setup_qr_tab_scroll
    cls.apply_qr_data_layout=apply_qr_layout
    cls.reset_qr_data_layout=reset_qr_layout
    cls.redraw_output=redraw
    cls.load_active_card_into_editor=load_editor
    cls.select_card=select_card
    cls.effective_display_mode=effective
    cls.set_live_qr_data=set_live
    cls.toggle_live_qr_data=toggle
    cls.draw_qr_data=draw_qr_data
    cls.draw_display_text=draw_display_text
    for typ,name in (('emoji','delete_sticker'),('image','delete_image_layer'),('text','delete_text_layer')):
        old=getattr(cls,name)
        setattr(cls,name,lambda self,_type=typ,_orig=old:self.delete_from_side(_type,_orig))
    cls.delete_from_side=delete_from_side

    # Selection refresh follows the currently displayed side and updates ONLY
    # checkboxes; it doesn't rewrite the editor's geometry values.
    for name in ('load_selected_sticker_into_controls','load_selected_image_into_controls','load_selected_text_layer_into_controls'):
        old=getattr(cls,name)
        def with_refresh(self,*args,_orig=old,**kwargs):
            result=_orig(self,*args,**kwargs)
            self.dualside_refresh_ui()
            return result
        setattr(cls,name,with_refresh)

__all__=['install','ensure_layer','ensure_card','side_snapshot','side_apply','ensure_layout','default_qr_layout']
