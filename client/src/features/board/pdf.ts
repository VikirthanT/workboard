const MARGIN = 10;
const GAP = 3;

/**
 * Draws the report sheet into an A4 landscape PDF and saves it. Each `[data-pdf-block]` is captured on its own
 * and placed top to bottom, starting a new page when the next block would not fit, so a row is never cut in half.
 * The libraries load on first use only.
 * shortcut: the PDF is an image of the sheet (text is not selectable), and one block taller than a page
 * (a very long summary table) runs off it; upgrade to a real text PDF / split that table if either matters.
 */
export async function downloadSheetAsPdf(sheet: HTMLElement, filename: string) {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([import('html2canvas-pro'), import('jspdf')]);
  const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  const pageW = pdf.internal.pageSize.getWidth() - MARGIN * 2;
  const pageBottom = pdf.internal.pageSize.getHeight() - MARGIN;
  const mmPerPx = pageW / sheet.offsetWidth;
  // The PDF is always light. That is done on html2canvas's own copy of the page, so the live page never flips.
  const lightClone = (doc: Document) => doc.documentElement.classList.remove('dark');

  let y = MARGIN;
  for (const block of sheet.querySelectorAll<HTMLElement>('[data-pdf-block]')) {
    const w = block.offsetWidth * mmPerPx;
    const h = block.offsetHeight * mmPerPx;
    if (y > MARGIN && y + h > pageBottom) {
      pdf.addPage();
      y = MARGIN;
    }
    const canvas = await html2canvas(block, { scale: 2, backgroundColor: null, onclone: lightClone });
    pdf.addImage(canvas.toDataURL('image/png'), 'PNG', MARGIN, y, w, h);
    y += h + GAP;
  }
  pdf.save(filename);
}
