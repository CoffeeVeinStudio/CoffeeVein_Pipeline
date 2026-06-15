"""
CA_QualifierWidget.py - DaVinci Resolve-style HSL Qualifier for Nuke
Embeds directly in node properties via PyCustom_Knob.

HDR SUPPORT:
- Saturation uses HSV formula (HDR-safe, always [0,1])
- Luminance uses Rec.709 weighted sum (HDR magnitude preserved)
- Luminance thresholds stored in LINEAR scene-linear space
- SDR Mode: slider is pure linear [0,1] (backwards compatible)
- HDR Mode: slider [0, 0.5] -> linear [0, 1], slider [0.5, 1.0] -> linear [1, 2^stops]
- Analyze button samples a 100x100 grid, picks mode/stops based on percentile
- Pick Color auto-bumps Lum Max and mode if sample exceeds current range
"""
import colorsys, math
try:
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui
try:
    import nuke
    IN_NUKE = True
except ImportError:
    IN_NUKE = False

C_BG=QtGui.QColor(46,46,46);C_GRAPH_BG=QtGui.QColor(24,24,24)
C_BORDER=QtGui.QColor(58,58,58);C_GRID=QtGui.QColor(38,38,38)
C_HANDLE=QtGui.QColor(160,160,160);C_HANDLE_HOV=QtGui.QColor(230,230,230)
C_HANDLE_ACT=QtGui.QColor(85,180,255);C_TEXT=QtGui.QColor(120,120,120)
C_TEXT_BRI=QtGui.QColor(190,190,190);C_DISABLED=QtGui.QColor(70,70,70)
C_HUE_FILL=QtGui.QColor(200,65,65,45);C_HUE_EDGE=QtGui.QColor(200,65,65,150);C_HUE_GLOW=QtGui.QColor(200,65,65,25)
C_SAT_FILL=QtGui.QColor(55,165,55,45);C_SAT_EDGE=QtGui.QColor(55,165,55,150);C_SAT_GLOW=QtGui.QColor(55,165,55,25)
C_LUM_FILL=QtGui.QColor(55,110,210,45);C_LUM_EDGE=QtGui.QColor(55,110,210,150);C_LUM_GLOW=QtGui.QColor(55,110,210,25)
C_SDR_TICK=QtGui.QColor(180,180,180,120)  # midpoint tick for HDR mode
C_DATA_MAX=QtGui.QColor(255,200,80,180)   # tick showing where detected max is
HR=5;GH=76;GM=10;FONT="Segoe UI, Helvetica Neue, Arial, sans-serif"
FALLOFF_LINEAR=0;FALLOFF_SMOOTH=1;FALLOFF_SHARP=2


def _falloff_curve(t, mode):
    """Apply the trapezoid soft-edge falloff curve."""
    t = max(0.0, min(1.0, t))
    if mode == FALLOFF_LINEAR: return t
    if mode == FALLOFF_SHARP: return t * t * t
    return t * t * (3.0 - 2.0 * t)  # FALLOFF_SMOOTH (default)


def _trap_alpha(val, lo, hi, lo_s, hi_s, is_hue=False, falloff=FALLOFF_SMOOTH):
    """Compute the trapezoid alpha for a single channel value.
    Mirrors what the painter draws and (closely enough) what the Blink
    kernel evaluates. Used by Smart Remove to score candidate shrinks
    against actual image samples."""
    wrap = is_hue and lo > hi
    if wrap:
        # Wrap mode: range = [lo, 1] U [0, hi]; soft falloff is INSIDE the
        # range near the gap edges (lo and hi).
        if hi < val < lo: return 0.0  # in the gap
        if val <= hi:
            d = hi - val  # distance going right toward the gap
            if d < hi_s:
                return _falloff_curve(d / hi_s, falloff) if hi_s > 1e-9 else 1.0
            return 1.0
        else:  # val >= lo
            d = val - lo  # distance going right from gap edge
            if d < lo_s:
                return _falloff_curve(d / lo_s, falloff) if lo_s > 1e-9 else 1.0
            return 1.0
    else:
        if val < lo - lo_s or val > hi + hi_s: return 0.0
        if lo <= val <= hi: return 1.0
        if val < lo:
            t = (val - (lo - lo_s)) / lo_s if lo_s > 1e-9 else 1.0
            return _falloff_curve(t, falloff)
        else:
            t = ((hi + hi_s) - val) / hi_s if hi_s > 1e-9 else 1.0
            return _falloff_curve(t, falloff)


def _fmt_lin(v):
    """Adaptive linear value formatting for HDR."""
    av = abs(v)
    if av < 0.01: return f"{v:.4f}"
    if av < 10: return f"{v:.2f}"
    if av < 100: return f"{v:.1f}"
    return f"{v:.0f}"


class TrapezoidRange(QtWidgets.QWidget):
    changed=QtCore.Signal()
    def __init__(self,label,fill,edge,glow,is_hue=False,is_lum=False,parent=None):
        super().__init__(parent)
        self.label=label;self._fill=fill;self._edge=edge;self._glow=glow
        self._is_hue=is_hue;self._is_lum=is_lum;self._on=True
        self.lo=0.0;self.hi=1.0;self.lo_s=0.05;self.hi_s=0.05
        self.falloff=FALLOFF_SMOOTH
        # HDR state (only relevant when is_lum=True)
        self._mode='SDR'      # 'SDR' | 'HDR'
        self._stops=8         # HDR top-half covers 2^stops above white
        self._lum_max_info=1.0  # last analyzed or bumped max, for display tick
        self._drag=None;self._hover=None;self._dx0=0;self._snap={};self._click_offset=0.0
        self.setMinimumHeight(GH+32);self.setMaximumHeight(GH+32);self.setMouseTracking(True)

    # ---- HDR configuration ----
    def set_hdr_mode(self,mode,stops=None,lum_max=None):
        """Configure HDR behavior. Safe to call repeatedly."""
        changed=False
        if mode in('SDR','HDR') and mode!=self._mode:
            self._mode=mode;changed=True
            # When switching to SDR, clamp any HDR values back into [0,1]
            if mode=='SDR':
                self.lo=max(0.0,min(1.0,self.lo))
                self.hi=max(0.0,min(1.0,self.hi))
        if stops is not None and stops!=self._stops:
            self._stops=max(2,min(12,int(stops)));changed=True
        if lum_max is not None and lum_max!=self._lum_max_info:
            self._lum_max_info=max(0.0,float(lum_max));changed=True
        if changed: self.update()

    def _max_val(self):
        """Upper bound of the value space for this channel."""
        if self._is_lum and self._mode=='HDR': return pow(2.0,self._stops)
        return 1.0

    def _val_to_slider(self,v):
        """Convert a value in the channel's native space to slider [0,1]."""
        if not(self._is_lum and self._mode=='HDR'):
            return max(0.0,min(1.0,v))
        if v<=0.0: return 0.0
        if v<=1.0: return v*0.5   # SDR half
        stops_above=math.log(max(v,1e-6),2.0)
        return min(1.0,0.5+stops_above/(2.0*self._stops))

    def _slider_to_val(self,s):
        """Convert slider [0,1] to value in channel's native space."""
        if not(self._is_lum and self._mode=='HDR'):
            return max(0.0,min(1.0,s))
        s=max(0.0,min(1.0,s))
        if s<=0.5: return s*2.0
        stops_above=(s-0.5)*2.0*self._stops
        return pow(2.0,stops_above)

    def _gr(self): return QtCore.QRectF(GM,18,self.width()-GM*2,GH)
    def _v2x(self,v): r=self._gr();return r.left()+self._val_to_slider(v)*r.width()
    def _x2v(self,x): r=self._gr();s=(x-r.left())/r.width();return self._slider_to_val(s)
    def _wrap(self): return self._is_hue and self.lo>self.hi

    def _handles(self):
        r=self._gr();b=r.bottom();t=r.top()+3;mv=self._max_val()
        if self._wrap():
            return {'lo_s':(self._v2x(min(1.0,self.lo+self.lo_s)),b),'lo':(self._v2x(self.lo),t),'hi':(self._v2x(self.hi),t),'hi_s':(self._v2x(max(0.0,self.hi-self.hi_s)),b)}
        return {'lo_s':(self._v2x(max(0.0,self.lo-self.lo_s)),b),'lo':(self._v2x(self.lo),t),'hi':(self._v2x(self.hi),t),'hi_s':(self._v2x(min(mv,self.hi+self.hi_s)),b)}

    def _hit(self,p):
        for n,(hx,hy) in self._handles().items():
            if abs(p.x()-hx)<HR+5 and abs(p.y()-hy)<HR+7: return n
        r=self._gr()
        if self._wrap():
            lx=self._v2x(self.lo);hx=self._v2x(self.hi);x0=self._v2x(0);x1=self._v2x(1)
            if (lx<=p.x()<=x1 or x0<=p.x()<=hx) and r.top()<p.y()<r.bottom(): return 'range'
        else:
            lx,hx=self._v2x(self.lo),self._v2x(self.hi)
            if lx<p.x()<hx and r.top()<p.y()<r.bottom(): return 'range'
        return None

    def _curve_pts(self,x0,y0,x1,y1,steps=12):
        pts=[]
        for i in range(steps+1):
            t=i/float(steps)
            if self.falloff==FALLOFF_LINEAR: f=t
            elif self.falloff==FALLOFF_SHARP: f=t*t*t
            else: f=t*t*(3.0-2.0*t)
            pts.append((x0+(x1-x0)*t, y0+(y1-y0)*f))
        return pts

    def paintEvent(self,e):
        p=QtGui.QPainter(self);p.setRenderHint(QtGui.QPainter.Antialiasing)
        r=self._gr();mv=self._max_val()
        f=p.font();f.setFamily(FONT);f.setPixelSize(10);f.setBold(True);p.setFont(f)
        p.setPen(C_TEXT_BRI if self._on else C_DISABLED);p.drawText(GM,13,self.label.upper())
        # HDR badge on luminance channel
        if self._is_lum and self._mode=='HDR' and self._on:
            f_h=QtGui.QFont(f);f_h.setBold(True);f_h.setPixelSize(8);p.setFont(f_h)
            p.setPen(QtGui.QColor(200,160,80))
            p.drawText(GM+int(p.fontMetrics().horizontalAdvance(self.label.upper()))+6,13,f"HDR \u00b7 {self._stops} STOPS")
        if not self._on:
            f2=QtGui.QFont(f);f2.setBold(False);f2.setPixelSize(9);p.setFont(f2)
            p.setPen(C_DISABLED);p.drawText(int(r.right())-26,13,"OFF")
        if self._on:
            f3=QtGui.QFont(f);f3.setBold(False);f3.setPixelSize(8);p.setFont(f3)
            p.setPen(QtGui.QColor(90,90,90))
            p.drawText(int(r.right())-22,13,{FALLOFF_LINEAR:"LIN",FALLOFF_SMOOTH:"SMT",FALLOFF_SHARP:"SHP"}.get(self.falloff,""))
        p.setPen(QtCore.Qt.NoPen);p.setBrush(C_GRAPH_BG);p.drawRoundedRect(r.toRect(),4,4)
        if self._is_hue:
            for i in range(int(r.width())):
                h=i/r.width();rgb=colorsys.hsv_to_rgb(h,0.6,0.28)
                c=QtGui.QColor(int(rgb[0]*255),int(rgb[1]*255),int(rgb[2]*255),30)
                p.setPen(QtGui.QPen(c,1));x=int(r.left())+i;p.drawLine(x,int(r.top()),x,int(r.bottom()))
        p.setPen(QtGui.QPen(C_GRID,1,QtCore.Qt.DotLine))
        for fv in [0.25,0.5,0.75]: x=int(r.left()+fv*r.width());p.drawLine(x,int(r.top()),x,int(r.bottom()))

        # HDR midpoint tick: marks linear 1.0 on the slider
        if self._is_lum and self._mode=='HDR' and self._on:
            mid_x=self._v2x(1.0)
            p.setPen(QtGui.QPen(C_SDR_TICK,1,QtCore.Qt.SolidLine))
            p.drawLine(int(mid_x),int(r.top()),int(mid_x),int(r.bottom()))
            f_t=QtGui.QFont(f);f_t.setBold(False);f_t.setPixelSize(7);p.setFont(f_t)
            p.setPen(QtGui.QColor(150,150,150,160));p.drawText(int(mid_x)-5,int(r.top())-2,"1.0")
            # Data-max tick: shows where the analyzed/bumped Lum Max sits
            if self._lum_max_info>0.001:
                dm_x=self._v2x(min(self._lum_max_info,mv*0.999))
                if dm_x>r.left() and dm_x<r.right():
                    p.setPen(QtGui.QPen(C_DATA_MAX,1,QtCore.Qt.DashLine))
                    p.drawLine(int(dm_x),int(r.top()),int(dm_x),int(r.bottom()))

        if not self._on: p.fillRect(r.toRect(),QtGui.QColor(46,46,46,180));p.end();return
        b=r.bottom();t=r.top()+3;wrap=self._wrap()

        def _trap(sl_x,lo_x,hi_x,sr_x):
            path=QtGui.QPainterPath()
            for px,py in self._curve_pts(sl_x,b,lo_x,t): path.lineTo(px,py) if path.elementCount()>0 else path.moveTo(px,py)
            path.lineTo(hi_x,t)
            for px,py in self._curve_pts(hi_x,t,sr_x,b)[1:]: path.lineTo(px,py)
            path.closeSubpath();return path

        paths=[]
        if wrap:
            hi_s_l=max(0.0,self.hi-self.hi_s);lo_s_r=min(1.0,self.lo+self.lo_s)
            p1=QtGui.QPainterPath();p1.moveTo(self._v2x(0),t);p1.lineTo(self._v2x(self.hi),t)
            for px,py in self._curve_pts(self._v2x(self.hi),t,self._v2x(hi_s_l),b)[1:]: p1.lineTo(px,py)
            p1.lineTo(self._v2x(0),b);p1.closeSubpath();paths.append(p1)
            p2=QtGui.QPainterPath()
            for px,py in self._curve_pts(self._v2x(lo_s_r),b,self._v2x(self.lo),t): p2.lineTo(px,py) if p2.elementCount()>0 else p2.moveTo(px,py)
            p2.lineTo(self._v2x(1),t);p2.lineTo(self._v2x(1),b);p2.closeSubpath();paths.append(p2)
        else:
            paths.append(_trap(self._v2x(max(0.0,self.lo-self.lo_s)),self._v2x(self.lo),self._v2x(self.hi),self._v2x(min(mv,self.hi+self.hi_s))))

        for path in paths:
            gp=QtGui.QPen(self._glow,6);gp.setJoinStyle(QtCore.Qt.RoundJoin);p.setPen(gp);p.setBrush(QtCore.Qt.NoBrush);p.drawPath(path)
            p.setPen(QtCore.Qt.NoPen);p.setBrush(self._fill);p.drawPath(path)
            p.setPen(QtGui.QPen(self._edge,1.5));p.setBrush(QtCore.Qt.NoBrush);p.drawPath(path)
        if not wrap:
            lx=self._v2x(self.lo);hx=self._v2x(self.hi)
            p.setPen(QtGui.QPen(QtGui.QColor(255,255,255,18),1));p.drawLine(QtCore.QPointF(lx+2,t+1),QtCore.QPointF(hx-2,t+1))
        for n,(hx2,hy) in self._handles().items():
            act=self._drag==n;hov=self._hover==n;col=C_HANDLE_ACT if act else(C_HANDLE_HOV if hov else C_HANDLE);rad=HR+(2 if act else(1 if hov else 0))
            if 'lo_s' in n or 'hi_s' in n:
                tri=QtGui.QPolygonF([QtCore.QPointF(hx2,hy-rad),QtCore.QPointF(hx2-rad,hy+rad*0.5),QtCore.QPointF(hx2+rad,hy+rad*0.5)])
                p.setPen(QtGui.QPen(col,1.5));p.setBrush(col if act else QtCore.Qt.NoBrush);p.drawPolygon(tri)
            else:
                p.setPen(QtGui.QPen(col,1.5));inner=QtGui.QColor(col.red(),col.green(),col.blue(),60 if not act else 200);p.setBrush(inner);p.drawEllipse(QtCore.QPointF(hx2,hy),rad,rad)
        f.setBold(False);f.setPixelSize(9);p.setFont(f);p.setPen(C_TEXT);ly=int(r.bottom())+11
        # Label formatting: hue in degrees, luminance adaptive linear, sat fixed 2dp
        if self._is_hue: fmt=lambda v:f"{v*360:.0f}\u00b0"
        elif self._is_lum: fmt=_fmt_lin
        else: fmt=lambda v:f"{v:.2f}"
        hpos=self._handles()
        if self._wrap():
            p.drawText(int(hpos['lo_s'][0])-14,ly,fmt(min(1,self.lo+self.lo_s)));p.drawText(int(hpos['hi_s'][0])-14,ly,fmt(max(0,self.hi-self.hi_s)))
        else:
            p.drawText(int(hpos['lo_s'][0])-14,ly,fmt(max(0.0,self.lo-self.lo_s)));p.drawText(int(hpos['hi_s'][0])-14,ly,fmt(min(mv,self.hi+self.hi_s)))
        p.drawText(int(hpos['lo'][0])-8,ly,fmt(self.lo));p.drawText(int(hpos['hi'][0])-8,ly,fmt(self.hi))
        p.setPen(QtGui.QPen(C_BORDER,1));p.setBrush(QtCore.Qt.NoBrush);p.drawRoundedRect(r.toRect(),4,4);p.end()

    def mousePressEvent(self,e):
        if not self._on or e.button()!=QtCore.Qt.LeftButton: return
        h=self._hit(e.pos())
        if h:
            self._drag=h;self._dx0=e.pos().x()
            self._snap=dict(lo=self.lo,hi=self.hi,lo_s=self.lo_s,hi_s=self.hi_s)
            # Offset between click point and handle position
            handle_pos_map={
                'lo':self._v2x(self.lo),
                'hi':self._v2x(self.hi),
                'lo_s':self._v2x(max(0.0,self.lo-self.lo_s)) if not self._wrap() else self._v2x(min(1.0,self.lo+self.lo_s)),
                'hi_s':self._v2x(min(self._max_val(),self.hi+self.hi_s)) if not self._wrap() else self._v2x(max(0.0,self.hi-self.hi_s)),
                'range':e.pos().x(),
            }
            handle_x=handle_pos_map.get(h,e.pos().x())
            self._click_offset=handle_x-e.pos().x()
            self.setCursor(QtCore.Qt.ClosedHandCursor);self.update()

    def mouseMoveEvent(self,e):
        if not self._on: return
        if self._drag:
            r=self._gr();s=self._snap;mv=self._max_val()
            # For HDR luminance, drag in value space (log-aware).
            # For hue/sat/SDR-lum, drag in slider space (original behavior).
            hdr=self._is_lum and self._mode=='HDR'
            if hdr and self._drag!='range':
                new_x=e.pos().x()+self._click_offset
                new_val=self._x2v(new_x)
                if self._drag=='lo':
                    self.lo=max(0.0,min(s['hi']-0.005,new_val))
                elif self._drag=='hi':
                    self.hi=max(s['lo']+0.005,min(mv,new_val))
                elif self._drag=='lo_s':
                    # soft handle sits at (lo - lo_s); derive new softness
                    self.lo_s=max(0.0,s['lo']-new_val)
                elif self._drag=='hi_s':
                    # soft handle sits at (hi + hi_s)
                    self.hi_s=max(0.0,new_val-s['hi'])
            elif hdr and self._drag=='range':
                start_val=self._x2v(self._dx0)
                curr_val=self._x2v(e.pos().x())
                delta_val=curr_val-start_val
                span=s['hi']-s['lo']
                nl=s['lo']+delta_val;nh=s['hi']+delta_val
                if nl<0: nl=0.0;nh=span
                if nh>mv: nh=mv;nl=mv-span
                self.lo=nl;self.hi=nh
            else:
                dv=(e.pos().x()-self._dx0)/r.width()
                if self._is_hue:
                    if self._drag=='lo': self.lo=(s['lo']+dv)%1.0
                    elif self._drag=='hi': self.hi=(s['hi']+dv)%1.0
                    elif self._drag=='lo_s':
                        if self._wrap(): self.lo_s=max(0.0,s['lo_s']+dv)
                        else: self.lo_s=max(0.0,s['lo_s']-dv)
                    elif self._drag=='hi_s':
                        if self._wrap(): self.hi_s=max(0.0,s['hi_s']-dv)
                        else: self.hi_s=max(0.0,s['hi_s']+dv)
                    elif self._drag=='range': self.lo=(s['lo']+dv)%1.0;self.hi=(s['hi']+dv)%1.0
                else:
                    if self._drag=='lo': self.lo=max(0.0,min(s['hi']-0.005,s['lo']+dv))
                    elif self._drag=='hi': self.hi=max(s['lo']+0.005,min(1.0,s['hi']+dv))
                    elif self._drag=='lo_s': np2=max(0.0,s['lo']-s['lo_s']+dv);self.lo_s=max(0.0,s['lo']-np2)
                    elif self._drag=='hi_s': np2=min(1.0,s['hi']+s['hi_s']+dv);self.hi_s=max(0.0,np2-s['hi'])
                    elif self._drag=='range':
                        span=s['hi']-s['lo'];nl=s['lo']+dv;nh=s['hi']+dv
                        if nl<0:nl=0;nh=span
                        if nh>1:nh=1;nl=1-span
                        self.lo=nl;self.hi=nh
            self.changed.emit();self.update()
        else:
            h=self._hit(e.pos())
            if h!=self._hover:
                self._hover=h;self.setCursor(QtCore.Qt.SizeHorCursor if h and h!='range' else QtCore.Qt.OpenHandCursor if h=='range' else QtCore.Qt.ArrowCursor);self.update()

    def mouseReleaseEvent(self,e):
        if self._drag: self._drag=None;self.setCursor(QtCore.Qt.ArrowCursor);self.update()

    def mouseDoubleClickEvent(self,e):
        if not self._on: return
        if self._hit(e.pos()) is None: self.falloff=(self.falloff+1)%3;self.changed.emit();self.update()

    def set_from_center(self,center,width=0.1,soft=0.04):
        half=width*0.5;mv=self._max_val()
        self.lo=max(0.0,center-half);self.hi=min(mv,center+half)
        self.lo_s=soft;self.hi_s=soft;self.changed.emit();self.update()

    # Add and Remove use a small eps buffer on either side of val.
    # - Add (expand_to): place lo at val - EPS so val sits inside the hard range
    #   with alpha = 1. The soft falloff on the OUTSIDE doesn't affect val.
    # - Remove (shrink_from): place lo at val + lo_s + EPS so the SOFT EDGE
    #   (new_lo - lo_s) clears val. Without the lo_s term, val stays inside
    #   the soft falloff zone — alpha is still non-zero — and the matte
    #   visibly doesn't change. This is the actual bug behind "Remove doesn't
    #   work on the alpha": the hard edge moves but softness still pulls val in.
    EPS = 0.005

    def expand_to(self, val):
        eps = self.EPS; mv = self._max_val()
        # Wrap-aware "is val already inside?" check for hue
        if self._wrap():
            if val >= self.lo or val <= self.hi: return  # already inside wrapped range
            # val is in the gap [hi, lo] — extend the nearer edge
            d_to_hi = val - self.hi
            d_to_lo = self.lo - val
            if d_to_hi <= d_to_lo: self.hi = min(1.0, val + eps)
            else: self.lo = max(0.0, val - eps)
        else:
            if val < self.lo: self.lo = max(0.0, val - eps)
            elif val > self.hi: self.hi = min(mv, val + eps)
        self.changed.emit(); self.update()

    def shrink_from(self, val):
        eps = self.EPS
        # "Can this val have its alpha reduced by shrinking?" check.
        # Anywhere in the soft+hard envelope counts (not just hard) — a val
        # sitting in the soft falloff still has alpha > 0 and pushing the
        # boundary past it drops alpha to 0.
        if self._wrap():
            # Wrap "outside" = the gap (hi, lo) — alpha already 0 there.
            if self.hi < val < self.lo: return
        else:
            if val < self.lo - self.lo_s or val > self.hi + self.hi_s: return

        if self._wrap():
            # Wrap: soft is INSIDE the range, so pushing the hard edge past val
            # by eps already puts val outside the trapezoid.
            d_lo = (val - self.lo) if val >= self.lo else (val + 1.0 - self.lo)
            d_hi = (self.hi - val) if val <= self.hi else (self.hi + 1.0 - val)
            if d_lo <= d_hi:
                self.lo = min(val + eps, 1.0)
            else:
                self.hi = max(val - eps, 0.0)
        else:
            # Non-wrap: soft is OUTSIDE the hard range. Push the hard edge past
            # val by (softness + eps) so the SOFT edge also clears val. This is
            # what makes Remove actually drop val's alpha to 0 — without it,
            # val sits in the soft falloff and Remove looks like a no-op.
            # The midpoint check uses val's relationship to the hard center,
            # which works whether val is inside the hard range or in soft.
            mid = (self.lo + self.hi) * 0.5
            if val <= mid:
                self.lo = min(val + self.lo_s + eps, self.hi - 0.005)
            else:
                self.hi = max(val - self.hi_s - eps, self.lo + 0.005)
        self.changed.emit(); self.update()

    def expand_soft_to(self, val):
        eps=0.005
        if val < self.lo:
            needed = self.lo - val + eps
            self.lo_s = max(self.lo_s, needed)
        if val > self.hi:
            needed = val - self.hi + eps
            self.hi_s = max(self.hi_s, needed)
        self.changed.emit(); self.update()

    def shrink_soft(self, amount=0.015):
        self.lo_s = max(0.0, self.lo_s - amount)
        self.hi_s = max(0.0, self.hi_s - amount)
        self.changed.emit(); self.update()


class GlobalSoftnessSlider(QtWidgets.QWidget):
    softnessChanged = QtCore.Signal(float)
    released = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._dragging = False
        self._hover = False
        self.setMinimumHeight(36)
        self.setMaximumHeight(36)
        self.setMouseTracking(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def _track_rect(self):
        return QtCore.QRectF(GM + 40, 18, self.width() - GM * 2 - 80, 6)

    def _handle_x(self):
        tr = self._track_rect()
        return tr.left() + (self._value * 0.5 + 0.5) * tr.width()

    def _x_to_val(self, x):
        tr = self._track_rect()
        return max(-1.0, min(1.0, ((x - tr.left()) / tr.width()) * 2.0 - 1.0))

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        tr = self._track_rect()
        f = p.font(); f.setFamily(FONT); f.setPixelSize(9); f.setBold(False); p.setFont(f)
        p.setPen(C_TEXT); p.drawText(GM, 23, "SOFT")
        grad = QtGui.QLinearGradient(tr.left(), 0, tr.right(), 0)
        grad.setColorAt(0.0, QtGui.QColor(200, 65, 65, 50))
        grad.setColorAt(0.35, QtGui.QColor(40, 40, 40))
        grad.setColorAt(0.5, QtGui.QColor(55, 55, 55))
        grad.setColorAt(0.65, QtGui.QColor(40, 40, 40))
        grad.setColorAt(1.0, QtGui.QColor(85, 180, 255, 50))
        p.setPen(QtCore.Qt.NoPen); p.setBrush(grad); p.drawRoundedRect(tr.toRect(), 3, 3)
        p.setPen(QtGui.QPen(C_BORDER, 1)); p.setBrush(QtCore.Qt.NoBrush); p.drawRoundedRect(tr.toRect(), 3, 3)
        cx = tr.left() + tr.width() * 0.5
        p.setPen(QtGui.QPen(QtGui.QColor(80, 80, 80), 1))
        p.drawLine(QtCore.QPointF(cx, tr.top() - 1), QtCore.QPointF(cx, tr.bottom() + 1))
        hx = self._handle_x()
        if abs(self._value) > 0.01:
            fill_col = QtGui.QColor(85, 180, 255, 80) if self._value > 0 else QtGui.QColor(200, 100, 80, 80)
            fill_left = min(cx, hx); fill_right = max(cx, hx)
            fill_rect = QtCore.QRectF(fill_left, tr.top(), fill_right - fill_left, tr.height())
            p.setPen(QtCore.Qt.NoPen); p.setBrush(fill_col); p.drawRoundedRect(fill_rect, 2, 2)
        hy = tr.center().y(); handle_r = 8 if self._dragging else (7 if self._hover else 6)
        if self._dragging or self._hover:
            glow_col = QtGui.QColor(85, 180, 255, 40) if self._value >= 0 else QtGui.QColor(200, 100, 80, 40)
            p.setPen(QtCore.Qt.NoPen); p.setBrush(glow_col); p.drawEllipse(QtCore.QPointF(hx, hy), handle_r + 4, handle_r + 4)
        handle_col = C_HANDLE_ACT if self._dragging else (C_HANDLE_HOV if self._hover else C_HANDLE)
        p.setPen(QtGui.QPen(handle_col, 1.5))
        inner = QtGui.QColor(handle_col.red(), handle_col.green(), handle_col.blue(), 120 if self._dragging else 60)
        p.setBrush(inner); p.drawEllipse(QtCore.QPointF(hx, hy), handle_r, handle_r)
        val_text = f"{self._value:+.2f}" if abs(self._value) > 0.005 else "0"
        p.setPen(C_TEXT_BRI if self._dragging else C_TEXT); p.drawText(int(tr.right()) + 8, 23, val_text)
        p.setPen(QtGui.QColor(90, 90, 90)); f.setPixelSize(8); p.setFont(f)
        p.drawText(int(tr.left()) - 4, int(tr.bottom()) + 10, "\u2212")
        p.drawText(int(tr.right()) - 3, int(tr.bottom()) + 10, "+")
        p.end()

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._dragging = True; self._value = self._x_to_val(e.pos().x())
            self.softnessChanged.emit(self._value); self.update()

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._value = self._x_to_val(e.pos().x())
            self.softnessChanged.emit(self._value); self.update()
        else:
            tr = self._track_rect(); expanded = tr.adjusted(-10, -10, 10, 10)
            was_hover = self._hover; self._hover = expanded.contains(e.pos())
            if was_hover != self._hover: self.update()

    def mouseReleaseEvent(self, e):
        if self._dragging: self._dragging = False; self.released.emit(); self.update()

    def reset(self): self._value = 0.0; self.update()


class QualifierWidget(QtWidgets.QWidget):
    def __init__(self,node=None,parent=None):
        super().__init__(parent);self._node=node
        # Flag set True the first time pull() successfully reads knob values.
        # Used by the retry timer in makeUI and the paintEvent backup so we
        # stop trying once the widget is in sync with the gizmo's saved state.
        self._pulled_ok = False
        self.setAttribute(QtCore.Qt.WA_StyledBackground,True);self.setStyleSheet("background:rgb(46,46,46);")
        layout=QtWidgets.QVBoxLayout(self);layout.setContentsMargins(0,4,0,4);layout.setSpacing(1)
        self.hue_w=TrapezoidRange("Hue",C_HUE_FILL,C_HUE_EDGE,C_HUE_GLOW,is_hue=True)
        self.sat_w=TrapezoidRange("Saturation",C_SAT_FILL,C_SAT_EDGE,C_SAT_GLOW)
        self.lum_w=TrapezoidRange("Luminance",C_LUM_FILL,C_LUM_EDGE,C_LUM_GLOW,is_lum=True)
        for w in[self.hue_w,self.sat_w,self.lum_w]: layout.addWidget(w);w.changed.connect(self._push)
        self._soft_slider = GlobalSoftnessSlider()
        layout.addWidget(self._soft_slider)
        self._soft_slider.softnessChanged.connect(self._on_global_softness)
        self._soft_slider.released.connect(self._on_soft_released)
        self._soft_base = {}

    def paintEvent(self, e):
        # Backup pull on first paint: if showEvent didn't fire (or fired before
        # the gizmo's invisible knobs were attached), this catches the case
        # where the widget would otherwise display its constructor defaults.
        if not self._pulled_ok and IN_NUKE:
            try: self.pull()
            except Exception: pass
        super().paintEvent(e)

    def _on_global_softness(self, val):
        delta = val * 0.3
        if not self._soft_base:
            self._soft_base = {
                'h_lo': self.hue_w.lo_s, 'h_hi': self.hue_w.hi_s,
                's_lo': self.sat_w.lo_s, 's_hi': self.sat_w.hi_s,
                'l_lo': self.lum_w.lo_s, 'l_hi': self.lum_w.hi_s,
            }
        self.hue_w.lo_s = max(0.0, self._soft_base['h_lo'] + delta)
        self.hue_w.hi_s = max(0.0, self._soft_base['h_hi'] + delta)
        self.sat_w.lo_s = max(0.0, self._soft_base['s_lo'] + delta)
        self.sat_w.hi_s = max(0.0, self._soft_base['s_hi'] + delta)
        # Luminance softness scales with its own magnitude in HDR mode
        lum_scale = max(1.0, self.lum_w._lum_max_info) if self.lum_w._mode == 'HDR' else 1.0
        self.lum_w.lo_s = max(0.0, self._soft_base['l_lo'] + delta * lum_scale)
        self.lum_w.hi_s = max(0.0, self._soft_base['l_hi'] + delta * lum_scale)
        for w in [self.hue_w, self.sat_w, self.lum_w]: w.update()
        self._push()

    def _on_soft_released(self): self._soft_base = {}

    # HDR-safe colour decomposition matching the kernel.
    # Returns (H in [0,1], S_hsv in [0,1], L_rec709 in linear).
    @staticmethod
    def _rgb_to_hsl_hdr(r,g,b):
        mx=max(r,g,b);mn=min(r,g,b);d=mx-mn
        s = d/mx if mx>1e-6 else 0.0
        l = 0.2126*r + 0.7152*g + 0.0722*b
        if d<1e-6: h=0.0
        elif mx==r: h=(((g-b)/d) + (6.0 if g<b else 0.0))/6.0
        elif mx==g: h=(((b-r)/d) + 2.0)/6.0
        else:       h=(((r-g)/d) + 4.0)/6.0
        return h,s,l

    def apply_sample(self,r,g,b,mode='sample'):
        # Do NOT clamp to [0,1] — keep HDR values intact.
        h,s,l = self._rgb_to_hsl_hdr(r,g,b)

        # Auto-bump Lum Max / switch to HDR if sample exceeds current range.
        # Only fire on additive operations — Remove must not expand the lum range.
        if mode in ('sample', 'add'):
            if l > 1.0 and self.lum_w._mode == 'SDR':
                self._set_hdr_from_lum_max(l * 1.1)
                print(f"[CA Qualifier] Sample L={l:.3f} > 1.0 -> auto-switched to HDR Mode, Lum Max={l*1.1:.3f}")
            elif l > self.lum_w._lum_max_info and self.lum_w._mode == 'HDR':
                self._set_hdr_from_lum_max(l * 1.1)
                print(f"[CA Qualifier] Sample L={l:.3f} exceeds Lum Max -> bumped to {l*1.1:.3f}")

        # Proportional luminance window in HDR space
        if self.lum_w._mode == 'HDR' and l > 1.0:
            lum_w_width = 0.5 * l
            lum_w_soft  = 0.16 * l
        else:
            lum_w_width = 0.5
            lum_w_soft  = 0.16

        if mode=='sample':
            self.hue_w.set_from_center(h,0.08,0.04)
            self.sat_w.set_from_center(s,0.25,0.08)
            self.lum_w.set_from_center(l,lum_w_width,lum_w_soft)
        elif mode=='add':
            self.hue_w.expand_to(h);self.sat_w.expand_to(s);self.lum_w.expand_to(l)
        elif mode=='remove':
            self._smart_remove(h, s, l)
        elif mode=='soft_add':
            self.hue_w.expand_soft_to(h);self.sat_w.expand_soft_to(s);self.lum_w.expand_soft_to(l)
        elif mode=='soft_remove':
            self.hue_w.shrink_soft();self.sat_w.shrink_soft();self.lum_w.shrink_soft()
        self._push()

    # ---------------- Smart Remove ----------------

    def _simulate_shrink_bounds(self, w, val):
        """Compute (new_lo, new_hi) the way shrink_from would, without actually
        modifying the widget. Used by Smart Remove to score candidates before
        committing to one."""
        new_lo, new_hi = w.lo, w.hi
        if w._wrap():
            d_lo = (val - w.lo) if val >= w.lo else (val + 1.0 - w.lo)
            d_hi = (w.hi - val) if val <= w.hi else (w.hi + 1.0 - val)
            if d_lo <= d_hi:
                new_lo = min(val + w.EPS, 1.0)
            else:
                new_hi = max(val - w.EPS, 0.0)
        else:
            mid = (w.lo + w.hi) * 0.5
            if val <= mid:
                new_lo = min(val + w.lo_s + w.EPS, w.hi - 0.005)
            else:
                new_hi = max(val - w.hi_s - w.EPS, w.lo + 0.005)
        return new_lo, new_hi

    def _sample_input_grid(self, n=30):
        """Sample the gizmo's input on an n×n grid. Returns a list of (h,s,l)
        tuples or None if input isn't available. Used by Smart Remove to
        estimate which channel-shrink causes the least collateral alpha loss."""
        if not IN_NUKE or not self._node:
            return None
        inp = self._node.input(0)
        if inp is None:
            return None
        try:
            bbox = inp.bbox()
            x0, y0 = bbox.x(), bbox.y()
            w_dim, h_dim = bbox.w(), bbox.h()
        except Exception:
            return None
        if w_dim <= 0 or h_dim <= 0:
            return None
        samples = []
        for iy in range(n):
            py = y0 + (iy + 0.5) * h_dim / n
            for ix in range(n):
                px = x0 + (ix + 0.5) * w_dim / n
                try:
                    r = inp.sample('red', px, py)
                    g = inp.sample('green', px, py)
                    b = inp.sample('blue', px, py)
                except Exception:
                    continue
                ph, ps, pl = self._rgb_to_hsl_hdr(r, g, b)
                # Filter NaN / inf
                if not (ph == ph and ps == ps and pl == pl): continue
                if abs(pl) > 1e9: continue
                samples.append((ph, ps, pl))
        return samples

    def _smart_remove(self, h_v, s_v, l_v):
        """Pick the channel whose shrink minimizes total alpha loss across the
        actual input image, then shrink only that channel.

        How it works: total alpha = h_a · s_a · l_a. Shrinking one channel only
        changes that channel's alpha; the other two are constant per pixel.
        So per-pixel alpha loss = (drop in shrunk channel) × (other two alphas).
        Sample the input on a grid, compute this loss for each candidate channel,
        pick the smallest. This naturally favors the channel whose shrunk band
        contains the fewest other-color pixels — what 'smart' means here:
        keep the rest of the matte intact.

        Falls back to a heuristic if no input is connected."""
        # Pre-flight: compute the sample's actual alpha contribution from each
        # channel. If any channel reports α ≈ 0 then the sample is genuinely
        # outside the trapezoid (hard + soft) on that channel, and total alpha
        # is already 0 — nothing for Remove to do. Use _trap_alpha so we
        # correctly include the soft falloff zone (a sample sitting in the soft
        # edge has α > 0 and Remove SHOULD push the boundary further).
        hw, sw, lw = self.hue_w, self.sat_w, self.lum_w
        h_alpha = _trap_alpha(h_v, hw.lo, hw.hi, hw.lo_s, hw.hi_s,
                              is_hue=True, falloff=hw.falloff)
        s_alpha = _trap_alpha(s_v, sw.lo, sw.hi, sw.lo_s, sw.hi_s, falloff=sw.falloff)
        l_alpha = _trap_alpha(l_v, lw.lo, lw.hi, lw.lo_s, lw.hi_s, falloff=lw.falloff)
        EPS_ALPHA = 1e-4
        if h_alpha < EPS_ALPHA or s_alpha < EPS_ALPHA or l_alpha < EPS_ALPHA:
            zero_ch = ('Hue' if h_alpha < EPS_ALPHA else
                       'Sat' if s_alpha < EPS_ALPHA else 'Lum')
            print(f"[CA Qualifier] Remove: sample already outside {zero_ch} "
                  f"(h-α={h_alpha:.3f}, s-α={s_alpha:.3f}, l-α={l_alpha:.3f}, "
                  f"total≈0). Nothing to remove.")
            return

        samples = self._sample_input_grid(n=30)
        if samples and len(samples) > 0:
            self._smart_remove_pixel_based(h_v, s_v, l_v, samples)
        else:
            print("[CA Qualifier] Smart Remove: no input connected or sampling failed — using heuristic.")
            self._smart_remove_heuristic(h_v, s_v, l_v)

    def _smart_remove_pixel_based(self, h_v, s_v, l_v, samples):
        hw, sw, lw = self.hue_w, self.sat_w, self.lum_w
        h_a = [_trap_alpha(p[0], hw.lo, hw.hi, hw.lo_s, hw.hi_s,
                            is_hue=True, falloff=hw.falloff) for p in samples]
        s_a = [_trap_alpha(p[1], sw.lo, sw.hi, sw.lo_s, sw.hi_s,
                            falloff=sw.falloff) for p in samples]
        l_a = [_trap_alpha(p[2], lw.lo, lw.hi, lw.lo_s, lw.hi_s,
                            falloff=lw.falloff) for p in samples]

        candidates = []
        channel_specs = [
            (0, hw, h_v, 'Hue', h_a, True),
            (1, sw, s_v, 'Sat', s_a, False),
            (2, lw, l_v, 'Lum', l_a, False),
        ]
        for ch_idx, w, val, name, ch_alphas, is_hue in channel_specs:
            new_lo, new_hi = self._simulate_shrink_bounds(w, val)
            new_ch_alphas = [_trap_alpha(samples[i][ch_idx], new_lo, new_hi,
                                          w.lo_s, w.hi_s, is_hue=is_hue,
                                          falloff=w.falloff)
                             for i in range(len(samples))]
            if ch_idx == 0:   other = [s_a[i] * l_a[i] for i in range(len(samples))]
            elif ch_idx == 1: other = [h_a[i] * l_a[i] for i in range(len(samples))]
            else:             other = [h_a[i] * s_a[i] for i in range(len(samples))]
            total_loss = 0.0
            for i in range(len(samples)):
                drop = ch_alphas[i] - new_ch_alphas[i]
                if drop > 0.0:
                    total_loss += drop * other[i]
            candidates.append((total_loss, w, val, name))

        candidates.sort(key=lambda x: x[0])
        best_loss, best_w, best_val, best_name = candidates[0]
        best_w.shrink_from(best_val)
        others = ", ".join(f"{n}={l:.2f}" for l, _, _, n in candidates[1:])
        print(f"[CA Qualifier] Smart Remove: shrunk {best_name} "
              f"(alpha-loss={best_loss:.2f}; alts: {others}; "
              f"{len(samples)} pixels sampled).")

    def _smart_remove_heuristic(self, h_v, s_v, l_v):
        """Fallback when no input is available: prefer the channel that was
        most recently expanded by Add (val sits ~EPS inside one edge), else
        pick the channel with smallest range-loss cost."""
        candidates = []
        for w, val, name in [(self.hue_w, h_v, 'Hue'),
                             (self.sat_w, s_v, 'Sat'),
                             (self.lum_w, l_v, 'Lum')]:
            if w._wrap():
                d_lo = (val - w.lo) if val >= w.lo else (val + 1.0 - w.lo)
                d_hi = (w.hi - val) if val <= w.hi else (w.hi + 1.0 - val)
                cost = min(d_lo, d_hi) + w.EPS
            else:
                d_lo = val - w.lo
                d_hi = w.hi - val
                cost = min(d_lo + w.lo_s, d_hi + w.hi_s) + w.EPS
            d_min = min(d_lo, d_hi)
            just_expanded = (w.EPS * 0.5) <= d_min <= (w.EPS * 1.5)
            candidates.append((cost, just_expanded, w, val, name))
        candidates.sort(key=lambda x: (not x[1], x[0]))
        best_cost, was_je, best_w, best_val, best_name = candidates[0]
        best_w.shrink_from(best_val)
        reason = "reverting recent Add" if was_je else "lowest range loss"
        print(f"[CA Qualifier] Smart Remove (heuristic): shrunk {best_name} "
              f"({reason}, cost={best_cost:.3f}).")


    def _set_hdr_from_lum_max(self, lum_max):
        """Set HDR mode, stops, and Lum Max on the widget AND push to node knobs."""
        if lum_max <= 1.0:
            mode='SDR';stops=8
        else:
            mode='HDR'
            stops=max(2, min(10, int(math.ceil(math.log(lum_max,2.0)))))
        self.lum_w.set_hdr_mode(mode, stops, lum_max)
        if IN_NUKE and self._node:
            try:
                self._node.knob('ca_lum_mode').setValue(0 if mode=='SDR' else 1)
                self._node.knob('ca_lum_stops').setValue(stops)
                self._node.knob('ca_lum_max').setValue(float(lum_max))
            except: pass

    def analyze_luminance(self, percentile='P99.9'):
        """Sample a grid on the group's input and return the requested percentile of Rec.709 L."""
        if not IN_NUKE or not self._node: return None
        inp = self._node.input(0)
        if inp is None:
            nuke.message("Connect an input to analyze.")
            return None
        try:
            bbox = inp.bbox()
            x0, y0 = bbox.x(), bbox.y()
            w, h = bbox.w(), bbox.h()
        except Exception as ex:
            nuke.message(f"Couldn't read input bbox: {ex}")
            return None
        if w <= 0 or h <= 0:
            nuke.message("Input has no image area.")
            return None
        n = 100
        lums = []
        task = nuke.ProgressTask("CA Qualifier: analyzing luminance")
        try:
            for iy in range(n):
                if task.isCancelled(): return None
                task.setProgress(int(100*iy/n))
                py = y0 + (iy + 0.5) * h / n
                for ix in range(n):
                    px = x0 + (ix + 0.5) * w / n
                    try:
                        r = inp.sample('red', px, py)
                        g = inp.sample('green', px, py)
                        b = inp.sample('blue', px, py)
                    except Exception:
                        continue
                    lum = 0.2126*r + 0.7152*g + 0.0722*b
                    if lum == lum and lum > -1e6 and lum < 1e9:  # NaN/inf filter
                        lums.append(lum)
        finally:
            del task
        if not lums: return None
        lums.sort()
        if percentile == 'Max':       idx = len(lums) - 1
        elif percentile == 'P99.9':   idx = int(len(lums) * 0.999)
        elif percentile == 'P99':     idx = int(len(lums) * 0.99)
        else:                         idx = len(lums) - 1
        return lums[min(idx, len(lums)-1)]

    def run_analyze(self):
        """Called by the Analyze button."""
        if not IN_NUKE or not self._node: return
        pct_knob = self._node.knob('ca_lum_percentile')
        percentile = pct_knob.value() if pct_knob else 'P99.9'
        result = self.analyze_luminance(percentile)
        if result is None:
            print("[CA Qualifier] Analyze: no result"); return
        self._set_hdr_from_lum_max(result)
        mode = self.lum_w._mode; stops = self.lum_w._stops
        print(f"[CA Qualifier] Analyze ({percentile}): Lum Max = {result:.3f}  -> {mode} Mode" + (f", {stops} stops" if mode=='HDR' else ""))

    def _push(self):
        if not IN_NUKE or not self._node: return
        try:
            n=self._node
            for prefix,w in[('hue',self.hue_w),('sat',self.sat_w),('lum',self.lum_w)]:
                n.knob(f'{prefix}_lo').setValue(w.lo);n.knob(f'{prefix}_hi').setValue(w.hi)
                n.knob(f'{prefix}_lo_s').setValue(w.lo_s);n.knob(f'{prefix}_hi_s').setValue(w.hi_s)
        except: pass

    def pull(self):
        """Read knob values from the gizmo node into the widget. Returns True
        if values were successfully loaded, False if the node wasn't ready
        (caller can use the bool to decide whether to retry)."""
        if not IN_NUKE: return False
        # Re-fetch node if missing or if the bound node doesn't have our knobs
        # (this happens when makeUI was called during a panel "probe" before the
        # gizmo's user knobs were fully attached, so self._node ended up being a
        # placeholder).
        try:
            need_refetch = (self._node is None) or (self._node.knob('hue_lo') is None)
        except Exception:
            need_refetch = True
        if need_refetch:
            try:
                fresh = nuke.thisNode()
                if fresh is not None and fresh.knob('hue_lo') is not None:
                    self._node = fresh
            except Exception:
                pass
        if not self._node:
            return False
        try:
            n = self._node
            # If the gizmo's invisible knobs still aren't present, bail without
            # clobbering widget state (would otherwise force defaults).
            if n.knob('hue_lo') is None:
                return False
            # HDR settings first so value clamping in TrapezoidRange uses the right _max_val.
            # Note: ca_lum_mode is an Enumeration_Knob — .value() returns the string
            # ('SDR'/'HDR'), so we use .getValue() which returns the numeric index.
            mode_idx = int(n.knob('ca_lum_mode').getValue()) if n.knob('ca_lum_mode') else 0
            stops = int(n.knob('ca_lum_stops').value()) if n.knob('ca_lum_stops') else 8
            lum_max = float(n.knob('ca_lum_max').value()) if n.knob('ca_lum_max') else 1.0
            self.lum_w.set_hdr_mode('HDR' if mode_idx==1 else 'SDR', stops, lum_max)
            for prefix,w in[('hue',self.hue_w),('sat',self.sat_w),('lum',self.lum_w)]:
                klo = n.knob(f'{prefix}_lo'); khi = n.knob(f'{prefix}_hi')
                klos = n.knob(f'{prefix}_lo_s'); khis = n.knob(f'{prefix}_hi_s')
                if klo and khi and klos and khis:
                    w.lo=klo.value(); w.hi=khi.value()
                    w.lo_s=klos.value(); w.hi_s=khis.value()
                    w.update()
                else:
                    # One of the four expected knobs is missing — the gizmo isn't
                    # fully constructed yet; tell the caller to retry.
                    return False
            self._pulled_ok = True
            return True
        except Exception as ex:
            print(f"[CA Qualifier] pull() error: {ex}")
            return False

    def showEvent(self, event):
        """Re-sync widget state from node knobs every time the panel becomes visible.
        Defends against script-load timing where makeUI's initial pull() might have
        run before all user knobs were attached to the node."""
        super().showEvent(event)
        # Force a re-pull on every panel show — knob values may have changed
        # while the panel was closed (via expressions, links, or another panel).
        self._pulled_ok = False
        self.pull()


class CA_QualifierKnob(object):
    """Controller for the PyCustom_Knob in the CA_HueQualifier gizmo.

    Robust against:
    - Being constructed before the node exists (nuke.thisNode() returning a
      placeholder during panel probe).
    - Widget creation failures (returns an empty QLabel placeholder so Nuke
      doesn't crash on the missing makeUI return value).
    - Stale references after node deletion (updateValue no-ops safely).
    """
    def __init__(self):
        self.widget = None

    def makeUI(self):
        try:
            node = nuke.thisNode() if IN_NUKE else None
            self.widget = QualifierWidget(node=node)
            if node is not None:
                # Immediate pull — works when knobs are already on the node
                try: self.widget.pull()
                except Exception as ex:
                    print(f"[CA Qualifier] initial pull() deferred: {ex}")
                # Retry chain — keeps trying until pull() returns True (knobs
                # found and values loaded), or we exhaust the attempt budget.
                # This handles all the timing variations: panel probe before
                # knobs are attached, slow script loads, deferred panel show.
                # Once pull() succeeds, the widget sets _pulled_ok = True and
                # the chain stops on its own.
                def _retry_pull(w=self.widget, attempts_left=15):
                    try:
                        if w is None or w._pulled_ok: return
                    except (RuntimeError, AttributeError):
                        return  # widget was deleted
                    try:
                        if w.pull(): return  # success — stop retrying
                    except (RuntimeError, AttributeError):
                        return
                    except Exception as ex:
                        print(f"[CA Qualifier] retry pull error: {ex}")
                    if attempts_left > 0:
                        QtCore.QTimer.singleShot(100, lambda: _retry_pull(w, attempts_left - 1))
                try:
                    # Kick off the retry chain after the current event loop tick
                    QtCore.QTimer.singleShot(0, _retry_pull)
                except Exception: pass
            return self.widget
        except Exception as ex:
            # Fall back to a placeholder so Nuke doesn't choke on a None return
            print(f"[CA Qualifier] makeUI error: {ex}")
            try:
                lbl = QtWidgets.QLabel(f"CA Qualifier UI failed to load:\n{ex}")
                lbl.setStyleSheet("color:#e66;padding:8px;")
                self.widget = lbl
                return lbl
            except Exception:
                return None

    def updateValue(self):
        if self.widget is None: return
        try:
            if hasattr(self.widget, 'pull'):
                # Force a re-pull on updateValue (called by Nuke when something
                # touches the knob). Don't gate on _pulled_ok — if the user just
                # changed an HDR knob via knobChanged, we want fresh values.
                self.widget._pulled_ok = False
                self.widget.pull()
        except Exception as ex:
            print(f"[CA Qualifier] updateValue error: {ex}")


def _on_apply(node):
    color=node.knob('ca_pick_color').value()
    mode_str=node.knob('ca_sample_mode').value()
    mode={'Set Range':'sample','Add to Range':'add','Remove from Range':'remove','Add Softness':'soft_add','Remove Softness':'soft_remove'}.get(mode_str,'sample')
    pck=node.knob('ca_qualifier_ui')
    if pck:
        obj=pck.getObject()
        if obj and hasattr(obj,'widget') and obj.widget: obj.widget.apply_sample(color[0],color[1],color[2],mode)
    print(f"[CA Qualifier] {mode_str}: R={color[0]:.3f} G={color[1]:.3f} B={color[2]:.3f}")


def _on_analyze(node):
    pck = node.knob('ca_qualifier_ui')
    if pck:
        obj = pck.getObject()
        if obj and hasattr(obj,'widget') and obj.widget:
            obj.widget.run_analyze()


def _on_apply_lum(node, auto_derive=True):
    """Push the node's Lum Mode / Stops / Lum Max knob values to the widget slider.

    When auto_derive=True (the default, used by the Update Sliders button), also
    automatically re-derives Mode and Stops to match the current Lum Max value.
    When called from the knobChanged callback (auto_derive=False), the user's
    explicit knob values are respected.
    """
    import math
    pck = node.knob('ca_qualifier_ui')
    if not pck: return
    obj = pck.getObject()
    if not (obj and hasattr(obj,'widget') and obj.widget): return

    if auto_derive:
        lum_max = node.knob('ca_lum_max').value()
        if lum_max <= 1.0:
            node.knob('ca_lum_mode').setValue(0)  # SDR
        else:
            node.knob('ca_lum_mode').setValue(1)  # HDR
            stops = max(2, min(10, int(math.ceil(math.log(lum_max, 2.0)))))
            node.knob('ca_lum_stops').setValue(stops)

    obj.widget.pull()
    lm = node.knob('ca_lum_mode').value()
    st = int(node.knob('ca_lum_stops').value())
    lx = node.knob('ca_lum_max').value()
    print(f"[CA Qualifier] Sliders updated: {lm} Mode, Stops={st}, Lum Max={lx:.3f}")