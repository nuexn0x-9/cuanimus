/**
 * CUANIMUS Web Control Center — High-Performance Canvas Candlestick Chart Engine.
 * Supports multi-timeframe candles, volume bars, EMA overlays, ATR bands,
 * dynamic Stop Loss / Take Profit target lines, Order Blocks, and crosshairs.
 */

class CuanimusChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.candles = [];
    this.indicators = {};
    this.hoverIndex = -1;
    this.mousePos = { x: -1, y: -1 };

    // Overlay display toggles
    this.options = {
      showEma: true,
      showVolume: true,
      showLevels: true,
      showOrderBlock: true,
    };

    this.colors = {
      bg: '#0c101a',
      grid: '#1a2233',
      text: '#64748b',
      bull: '#00c076',
      bear: '#f73859',
      ema20: '#38bdf8',
      ema50: '#a855f7',
      sl: '#f43f5e',
      tp: '#10b981',
      orderBlock: 'rgba(0, 192, 118, 0.12)',
      crosshair: '#475569'
    };

    this._bindEvents();
    this.resize();
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width;
    this.height = rect.height;
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.ctx.scale(dpr, dpr);
    this.render();
  }

  _bindEvents() {
    window.addEventListener('resize', () => this.resize());

    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      this.mousePos = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      };
      this.render();
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.mousePos = { x: -1, y: -1 };
      this.hoverIndex = -1;
      this.render();
    });
  }

  setData(data) {
    this.candles = data.candles || [];
    this.indicators = data.indicators || {};
    this.symbol = data.symbol || 'MARKET';
    this.timeframe = data.timeframe || '15m';
    this.render();
  }

  render() {
    if (!this.ctx || !this.candles.length) return;
    const ctx = this.ctx;
    const w = this.width;
    const h = this.height;

    // Clear background
    ctx.fillStyle = this.colors.bg;
    ctx.fillRect(0, 0, w, h);

    const paddingRight = 65;
    const paddingBottom = 26;
    const chartW = w - paddingRight;
    const chartH = h - paddingBottom;
    const volHeight = 60;
    const priceH = chartH - volHeight;

    // Determine min/max price
    let minP = Infinity;
    let maxP = -Infinity;
    let maxVol = 0;

    for (const c of this.candles) {
      if (c.low < minP) minP = c.low;
      if (c.high > maxP) maxP = c.high;
      if (c.volume > maxVol) maxVol = c.volume;
    }

    // Expand price range by 5%
    const pMargin = (maxP - minP) * 0.05 || 1.0;
    minP -= pMargin;
    maxP += pMargin;

    const priceToY = (p) => priceH - ((p - minP) / (maxP - minP)) * priceH;
    const yToPrice = (y) => maxP - (y / priceH) * (maxP - minP);

    // 1. Draw Grid Lines
    ctx.strokeStyle = this.colors.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = this.colors.text;
    ctx.font = '10px monospace';
    ctx.textAlign = 'left';

    const priceSteps = 6;
    for (let i = 0; i <= priceSteps; i++) {
      const pVal = minP + (i / priceSteps) * (maxP - minP);
      const y = priceToY(pVal);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(chartW, y);
      ctx.stroke();

      // Price scale text on right
      ctx.fillText(pVal.toFixed(2), chartW + 8, y + 3);
    }

    // 2. Order Block shading if present
    if (this.options.showOrderBlock && this.indicators.order_block) {
      const ob = this.indicators.order_block;
      const obYTop = priceToY(ob.high);
      const obYBottom = priceToY(ob.low);
      ctx.fillStyle = this.colors.orderBlock;
      ctx.fillRect(0, obYTop, chartW, obYBottom - obYTop);
      ctx.strokeStyle = 'rgba(0, 192, 118, 0.4)';
      ctx.setLineDash([4, 2]);
      ctx.strokeRect(0, obYTop, chartW, obYBottom - obYTop);
      ctx.setLineDash([]);
    }

    // 3. Draw Candlesticks & Volume Bars
    const n = this.candles.length;
    const barW = Math.max(2, (chartW / n) * 0.7);
    const stepX = chartW / n;

    let hoverCandle = null;
    let hoverX = -1;

    for (let i = 0; i < n; i++) {
      const c = this.candles[i];
      const x = i * stepX + stepX / 2;
      const isBull = c.close >= c.open;
      const col = isBull ? this.colors.bull : this.colors.bear;

      // Check hover
      if (Math.abs(this.mousePos.x - x) < stepX / 2 && this.mousePos.x <= chartW) {
        hoverCandle = c;
        hoverX = x;
      }

      // Volume Bar
      if (this.options.showVolume && maxVol > 0) {
        const vH = (c.volume / maxVol) * (volHeight - 10);
        const vY = chartH - vH;
        ctx.fillStyle = isBull ? 'rgba(0, 192, 118, 0.25)' : 'rgba(247, 56, 89, 0.25)';
        ctx.fillRect(x - barW / 2, vY, barW, vH);
      }

      // Candlestick Wick
      ctx.strokeStyle = col;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(x, priceToY(c.high));
      ctx.lineTo(x, priceToY(c.low));
      ctx.stroke();

      // Candlestick Body
      const bodyTop = priceToY(Math.max(c.open, c.close));
      const bodyBottom = priceToY(Math.min(c.open, c.close));
      const bodyH = Math.max(1, bodyBottom - bodyTop);

      ctx.fillStyle = col;
      ctx.fillRect(x - barW / 2, bodyTop, barW, bodyH);
    }

    // 4. Draw EMA Overlays
    if (this.options.showEma) {
      // EMA 20
      ctx.strokeStyle = this.colors.ema20;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < n; i++) {
        const c = this.candles[i];
        if (c.ema20) {
          const x = i * stepX + stepX / 2;
          const y = priceToY(c.ema20);
          if (!started) { ctx.moveTo(x, y); started = true; }
          else { ctx.lineTo(x, y); }
        }
      }
      ctx.stroke();

      // EMA 50
      ctx.strokeStyle = this.colors.ema50;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      started = false;
      for (let i = 0; i < n; i++) {
        const c = this.candles[i];
        if (c.ema50) {
          const x = i * stepX + stepX / 2;
          const y = priceToY(c.ema50);
          if (!started) { ctx.moveTo(x, y); started = true; }
          else { ctx.lineTo(x, y); }
        }
      }
      ctx.stroke();
    }

    // 5. Draw SL & TP Target lines
    if (this.options.showLevels && this.indicators.stop_loss_marker) {
      const slY = priceToY(this.indicators.stop_loss_marker);
      ctx.strokeStyle = this.colors.sl;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(0, slY);
      ctx.lineTo(chartW, slY);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = this.colors.sl;
      ctx.fillText(`SL: ${this.indicators.stop_loss_marker}`, chartW + 8, slY + 3);
    }

    if (this.options.showLevels && this.indicators.take_profit_marker) {
      const tpY = priceToY(this.indicators.take_profit_marker);
      ctx.strokeStyle = this.colors.tp;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(0, tpY);
      ctx.lineTo(chartW, tpY);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = this.colors.tp;
      ctx.fillText(`TP: ${this.indicators.take_profit_marker}`, chartW + 8, tpY + 3);
    }

    // 6. Draw Interactive Crosshairs & Info Tooltip
    if (hoverCandle && hoverX > 0 && this.mousePos.y >= 0 && this.mousePos.y <= chartH) {
      const mouseY = this.mousePos.y;

      // Crosshair lines
      ctx.strokeStyle = this.colors.crosshair;
      ctx.setLineDash([2, 2]);
      ctx.beginPath();
      ctx.moveTo(hoverX, 0);
      ctx.lineTo(hoverX, chartH);
      ctx.moveTo(0, mouseY);
      ctx.lineTo(chartW, mouseY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Current mouse price badge on scale
      const hoverPrice = yToPrice(mouseY);
      ctx.fillStyle = '#222f3e';
      ctx.fillRect(chartW + 2, mouseY - 9, paddingRight - 4, 18);
      ctx.fillStyle = '#fff';
      ctx.fillText(hoverPrice.toFixed(2), chartW + 8, mouseY + 4);

      // Tooltip header on top left
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(8, 8, 380, 22);
      ctx.strokeStyle = '#334155';
      ctx.strokeRect(8, 8, 380, 22);

      ctx.font = '11px monospace';
      ctx.fillStyle = '#94a3b8';
      ctx.fillText(`${hoverCandle.date}`, 14, 23);
      ctx.fillStyle = '#fff';
      ctx.fillText(`O: ${hoverCandle.open}  H: ${hoverCandle.high}  L: ${hoverCandle.low}  C: ${hoverCandle.close}`, 130, 23);
    }
  }
}

window.CuanimusChart = CuanimusChart;
