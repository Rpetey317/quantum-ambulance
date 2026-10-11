export class MetricMap {
  constructor(element, onSelect, onMove) {
    this.element = element;
    this.canvas = element.querySelector("canvas");
    this.layer = element.querySelector(".markers");
    this.onSelect = onSelect;
    this.onMove = onMove;
    this.markers = new Map();
    this.drag = null;
    this.observer = new ResizeObserver(() => this.draw());
    this.observer.observe(element);
  }
  update(data, bounds, overlay, active, color) {
    this.data = data;
    this.bounds = bounds;
    this.overlay = overlay;
    this.active = active;
    this.color = color;
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
        covered = !this.drag && this.overlay.zones.has(z.id);
      ctx.beginPath();
      ctx.arc(x, y, covered ? 2.7 : 1.7, 0, 2 * Math.PI);
      ctx.fillStyle = covered ? this.color : "#24343d55";
      ctx.fill();
    }
    ctx.restore();
    const length = 10 ** Math.floor(Math.log10((b.maxX - b.minX) / 4));
    ctx.strokeStyle = "#24343d";
    ctx.beginPath();
    ctx.moveTo(12, t.height - 14);
    ctx.lineTo(12 + length * t.scale, t.height - 14);
    ctx.stroke();
    ctx.font = "11px Aptos, sans-serif";
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
