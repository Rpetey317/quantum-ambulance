function abstractBackground(ctx, x, y, w, h) {
  const px = (u) => x + u * w,
    py = (v) => y + v * h;
  ctx.fillStyle = "#edf1e7";
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = "#f6f4ea";
  for (const [a, b, cw, ch] of [
    [0.05, 0.07, 0.3, 0.22],
    [0.44, 0.05, 0.24, 0.18],
    [0.72, 0.09, 0.23, 0.27],
    [0.07, 0.4, 0.24, 0.2],
    [0.4, 0.3, 0.3, 0.24],
    [0.74, 0.46, 0.2, 0.18],
    [0.1, 0.74, 0.26, 0.18],
    [0.46, 0.7, 0.24, 0.22],
    [0.76, 0.74, 0.18, 0.18],
  ])
    ctx.fillRect(px(a), py(b), cw * w, ch * h);
  ctx.fillStyle = "#d4e6c8";
  for (const [cx, cy, rx, ry] of [
    [0.19, 0.51, 0.09, 0.07],
    [0.84, 0.25, 0.1, 0.09],
    [0.56, 0.88, 0.08, 0.06],
  ]) {
    ctx.beginPath();
    ctx.ellipse(px(cx), py(cy), rx * w, ry * h, 0, 0, 2 * Math.PI);
    ctx.fill();
  }
  ctx.fillStyle = "#c2dbe4";
  ctx.beginPath();
  ctx.moveTo(px(0), py(0.64));
  ctx.bezierCurveTo(px(0.3), py(0.56), px(0.55), py(0.68), px(1), py(0.53));
  ctx.lineTo(px(1), py(0.68));
  ctx.bezierCurveTo(px(0.55), py(0.83), px(0.3), py(0.7), px(0), py(0.8));
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = Math.max(1.5, w * 0.005);
  ctx.beginPath();
  ctx.moveTo(px(0), py(0.34));
  ctx.lineTo(px(1), py(0.4));
  ctx.moveTo(px(0.66), py(0));
  ctx.lineTo(px(0.62), py(1));
  ctx.stroke();
}

export class MetricMap {
  constructor(element, onSelect, onMove) {
    this.element = element;
    this.canvas = element.querySelector("canvas");
    this.layer = element.querySelector(".markers");
    this.onSelect = onSelect;
    this.onMove = onMove;
    this.markers = new Map();
    this.drag = null;
    this.background = { mode: "plain" };
    this.observer = new ResizeObserver(() => this.draw());
    this.observer.observe(element);
  }
  update(data, bounds, overlay, active, color, background) {
    this.data = data;
    this.bounds = bounds;
    this.overlay = overlay;
    this.active = active;
    this.color = color;
    if (background) this.background = background;
    this.draw();
  }
  transform() {
    const b = this.bounds,
      width = this.element.clientWidth,
      height = this.element.clientHeight;
    const scale = Math.min(
      (width - 48) / (b.maxX - b.minX),
      (height - 48) / (b.maxY - b.minY),
    );
    const ox = (width - (b.maxX - b.minX) * scale) / 2;
    const oy = (height - (b.maxY - b.minY) * scale) / 2;
    return {
      scale,
      ox,
      oy,
      width,
      height,
      point: (p) => [
        ox + (p.x_km - b.minX) * scale,
        height - oy - (p.y_km - b.minY) * scale,
      ],
      world: (x, y) => ({
        x_km: Math.max(b.minX, Math.min(b.maxX, b.minX + (x - ox) / scale)),
        y_km: Math.max(
          b.minY,
          Math.min(b.maxY, b.minY + (height - oy - y) / scale),
        ),
      }),
    };
  }
  draw() {
    if (!this.data) {
      this.layer.replaceChildren();
      this.markers.clear();
      this.canvas
        .getContext("2d")
        .clearRect(0, 0, this.canvas.width, this.canvas.height);
      return;
    }
    const t = this.transform(),
      ratio = window.devicePixelRatio || 1;
    this.canvas.width = t.width * ratio;
    this.canvas.height = t.height * ratio;
    const ctx = this.canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    const b = this.bounds;
    ctx.strokeStyle = "#c7d5dd";
    ctx.lineWidth = 1;
    ctx.strokeRect(
      t.ox,
      t.oy,
      (b.maxX - b.minX) * t.scale,
      (b.maxY - b.minY) * t.scale,
    );
    ctx.save();
    ctx.beginPath();
    ctx.rect(
      t.ox,
      t.oy,
      (b.maxX - b.minX) * t.scale,
      (b.maxY - b.minY) * t.scale,
    );
    ctx.clip();
    const bg = this.background,
      framed = bg.mode === "image";
    if (framed && bg.image?.complete && bg.image.naturalWidth) {
      const ib = bg.bounds,
        [x0, y0] = t.point({ x_km: ib.minX, y_km: ib.maxY }),
        [x1, y1] = t.point({ x_km: ib.maxX, y_km: ib.minY });
      ctx.drawImage(bg.image, x0, y0, x1 - x0, y1 - y0);
    } else if (bg.mode === "abstract")
      abstractBackground(
        ctx,
        t.ox,
        t.oy,
        (b.maxX - b.minX) * t.scale,
        (b.maxY - b.minY) * t.scale,
      );
    if (!this.drag)
      for (const site of this.data.sites.filter((p) =>
        this.overlay.sites.has(p.id),
      )) {
        const [x, y] = t.point(site);
        ctx.beginPath();
        ctx.arc(x, y, this.data.radius_km * t.scale, 0, 2 * Math.PI);
        ctx.fillStyle = this.color + "13";
        ctx.fill();
        ctx.strokeStyle = this.color + "99";
        ctx.stroke();
      }
    // Display all original centroids; this layer never changes coverage inputs.
    for (const z of this.data.zones) {
      const [x, y] = t.point(z),
        covered = !this.drag && this.overlay.zones.has(z.id),
        r = covered ? 2.7 : 1.7;
      if (framed) {
        ctx.beginPath();
        ctx.arc(x, y, r + 1.3, 0, 2 * Math.PI);
        ctx.fillStyle = "#f3f7fa99";
        ctx.fill();
      }
      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.fillStyle = covered ? this.color : framed ? "#24343dcc" : "#24343d55";
      ctx.fill();
    }
    ctx.restore();
    const length = 10 ** Math.floor(Math.log10((b.maxX - b.minX) / 4));
    if (framed) {
      ctx.strokeStyle = "#f3f7facc";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(12, t.height - 14);
      ctx.lineTo(12 + length * t.scale, t.height - 14);
      ctx.stroke();
    }
    ctx.strokeStyle = "#24343d";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(12, t.height - 14);
    ctx.lineTo(12 + length * t.scale, t.height - 14);
    ctx.stroke();
    ctx.font = "11px Aptos, sans-serif";
    if (framed) {
      ctx.strokeStyle = "#f3f7facc";
      ctx.lineWidth = 3;
      ctx.strokeText(`${length} km`, 12, t.height - 21);
    }
    ctx.fillStyle = "#24343d";
    ctx.fillText(`${length} km`, 12, t.height - 21);
    for (const [id, el] of this.markers)
      if (!this.data.sites.some((p) => p.id === id)) {
        el.remove();
        this.markers.delete(id);
      }
    this.data.sites.forEach((site, index) => {
      let el = this.markers.get(site.id);
      if (!el) {
        el = document.createElement("button");
        el.type = "button";
        el.className = "marker";
        this.layer.append(el);
        this.markers.set(site.id, el);
        this.bind(el, site.id);
      }
      const current = this.drag?.id === site.id ? this.drag.position : site;
      const [x, y] = t.point(current);
      el.style.left = `${x}px`;
      el.style.top = `${y}px`;
      el.textContent = index;
      el.title = `Candidate ${index}: ${site.id}`;
      el.setAttribute(
        "aria-label",
        `Candidate ${index}, ${site.id}. Arrow keys move 100 metres; Shift moves 10 metres.`,
      );
      el.classList.toggle("active", site.id === this.active);
      el.classList.toggle(
        "selected",
        !this.drag && this.overlay.sites.has(site.id),
      );
      el.classList.toggle("dragging", this.drag?.id === site.id);
    });
  }
  bind(el, id) {
    el.addEventListener("click", () => this.onSelect(id));
    el.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || this.drag) return;
      this.onSelect(id);
      el.focus();
      this.drag = {
        id,
        position: { ...this.data.sites.find((p) => p.id === id) },
        pointer: event.pointerId,
      };
      el.setPointerCapture(event.pointerId);
      this.draw();
    });
    el.addEventListener("pointermove", (event) => {
      if (this.drag?.id !== id || this.drag.pointer !== event.pointerId) return;
      const rect = this.element.getBoundingClientRect();
      this.drag.position = this.transform().world(
        event.clientX - rect.left,
        event.clientY - rect.top,
      );
      this.draw();
    });
    const end = (event, cancel) => {
      if (this.drag?.id !== id || this.drag.pointer !== event.pointerId) return;
      const p = this.drag.position;
      this.drag = null;
      if (el.hasPointerCapture(event.pointerId))
        el.releasePointerCapture(event.pointerId);
      if (!cancel) this.onMove(id, p);
      this.draw();
    };
    el.addEventListener("pointerup", (e) => end(e, false));
    el.addEventListener("pointercancel", (e) => end(e, true));
    el.addEventListener("lostpointercapture", (e) => end(e, true));
    el.addEventListener("keydown", (event) => {
      const moves = {
        ArrowLeft: [-1, 0],
        ArrowRight: [1, 0],
        ArrowUp: [0, 1],
        ArrowDown: [0, -1],
      };
      if (!moves[event.key]) return;
      event.preventDefault();
      this.onSelect(id);
      const site = this.data.sites.find((p) => p.id === id),
        step = event.shiftKey ? 0.01 : 0.1;
      this.onMove(id, {
        x_km: site.x_km + moves[event.key][0] * step,
        y_km: site.y_km + moves[event.key][1] * step,
      });
    });
  }
}
