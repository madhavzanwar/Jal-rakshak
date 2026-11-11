/**
 * Client-side SitRep PDF (demo mode) using jsPDF's built-in Helvetica.
 * Loaded lazily — only when the user clicks "Export PDF".
 */
import { jsPDF } from 'jspdf';
import type { SitRep } from '../api/schema';

/** Built-in PDF fonts are WinAnsi only: map common typography and drop other non-Latin-1 chars. */
export function toLatin1(s: string): string {
  return s
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/[–—]/g, '-')
    .replace(/…/g, '...')
    .replace(/≥/g, '>=')
    .replace(/≤/g, '<=')
    .replace(/→/g, '->')
    .replace(/₹/g, 'Rs ')
    .replace(/[^\t\n\r\x20-\x7E\xA0-\xFF]/g, '');
}

export function buildSitrepPdf(rep: SitRep, opts: { cityName?: string; demo?: boolean } = {}): jsPDF {
  const doc = new jsPDF({ unit: 'pt', format: 'a4' });
  const W = doc.internal.pageSize.getWidth();
  const H = doc.internal.pageSize.getHeight();
  const M = 48;
  let y = 0;

  const header = () => {
    doc.setFillColor(11, 18, 32);
    doc.rect(0, 0, W, 64, 'F');
    doc.setTextColor(125, 211, 252);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(18);
    doc.text('Jal', M, 40);
    doc.setTextColor(255, 255, 255);
    doc.text('Rakshak', M + doc.getTextWidth('Jal'), 40);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    doc.setTextColor(203, 213, 225);
    doc.text(toLatin1(`Situation Report${opts.demo ? ' - DEMO (synthetic replay)' : ''}`), W - M, 36, { align: 'right' });
    y = 96;
  };
  const footer = (page: number, pages: number) => {
    doc.setFontSize(8);
    doc.setTextColor(100, 116, 139);
    doc.text('Decision support prototype - Not an official warning. Follow IMD/NDMA/SDMA. Data: Open-Meteo (GloFAS, ECMWF/ICON), (c) OpenStreetMap contributors.', M, H - 28);
    doc.text(`Page ${page} / ${pages}`, W - M, H - 28, { align: 'right' });
  };
  const ensure = (h: number) => {
    if (y + h > H - 60) {
      doc.addPage();
      header();
    }
  };
  const para = (text: string, size = 10.5, color: [number, number, number] = [30, 41, 59], gap = 6) => {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(size);
    doc.setTextColor(...color);
    const lines = doc.splitTextToSize(toLatin1(text), W - 2 * M) as string[];
    for (const ln of lines) {
      ensure(size * 1.45);
      doc.text(ln, M, y);
      y += size * 1.45;
    }
    y += gap;
  };

  header();
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(17);
  doc.setTextColor(15, 23, 42);
  for (const ln of doc.splitTextToSize(toLatin1(rep.title), W - 2 * M) as string[]) {
    doc.text(ln, M, y);
    y += 22;
  }
  para(`${opts.cityName ?? rep.city_id} - generated ${new Date(rep.generated_at).toUTCString()} - run ${rep.run_id}`, 9, [100, 116, 139], 10);
  para(rep.summary, 11.5, [15, 23, 42], 12);

  if (rep.key_figures.length) {
    const cols = 3;
    const cw = (W - 2 * M - (cols - 1) * 8) / cols;
    const rows = Math.ceil(rep.key_figures.length / cols);
    ensure(rows * 50);
    rep.key_figures.forEach((k, i) => {
      const cx = M + (i % cols) * (cw + 8);
      const cy = y + Math.floor(i / cols) * 50;
      doc.setFillColor(241, 245, 249);
      doc.roundedRect(cx, cy, cw, 42, 4, 4, 'F');
      doc.setFontSize(7.5);
      doc.setTextColor(100, 116, 139);
      doc.setFont('helvetica', 'normal');
      doc.text(toLatin1(k.label.toUpperCase()), cx + 8, cy + 14, { maxWidth: cw - 16 });
      doc.setFontSize(12);
      doc.setTextColor(15, 23, 42);
      doc.setFont('helvetica', 'bold');
      doc.text(toLatin1(k.value), cx + 8, cy + 32, { maxWidth: cw - 16 });
    });
    y += rows * 50 + 10;
  }

  for (const s of rep.sections) {
    ensure(40);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(12.5);
    doc.setTextColor(2, 132, 199);
    doc.text(toLatin1(s.heading), M, y);
    y += 17;
    para(s.body);
  }

  const pages = doc.getNumberOfPages();
  for (let i = 1; i <= pages; i++) {
    doc.setPage(i);
    footer(i, pages);
  }
  return doc;
}
