/**
 * Chat Export — PDF and DOCX export for chat transcripts.
 *
 * Uses jsPDF for PDF and the docx npm package for Word documents.
 * Both are client-side only (no server round-trip).
 */

export interface ChatMessage {
  id: string;
  role: 'user' | 'ai';
  content: string;
  timestamp: Date;
  sources?: Array<{ filename: string; page_num?: number; guideline_version?: string }>;
}

interface ExportOptions {
  messages: ChatMessage[];
  selectedVersions?: string[];
  sessionTitle?: string;
}

// ---------------------------------------------------------------------------
// PDF Export using jsPDF
// ---------------------------------------------------------------------------

export async function exportAsPDF({
  messages,
  selectedVersions = [],
  sessionTitle = 'Compliance AI Chat Transcript',
}: ExportOptions): Promise<void> {
  const { jsPDF } = await import('jspdf');
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 18;
  const contentW = pageW - margin * 2;
  let y = margin;

  const checkPageBreak = (needed = 12) => {
    if (y + needed > pageH - margin) {
      doc.addPage();
      y = margin;
    }
  };

  // ---- Cover / Header ----
  doc.setFillColor(8, 12, 20);
  doc.rect(0, 0, pageW, 42, 'F');

  doc.setTextColor(0, 212, 255);
  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  doc.text('The Compliance Leader', margin, 16);

  doc.setTextColor(180, 190, 210);
  doc.setFontSize(11);
  doc.setFont('helvetica', 'normal');
  doc.text(sessionTitle, margin, 25);

  doc.setTextColor(120, 130, 150);
  doc.setFontSize(8);
  doc.text(`Generated: ${new Date().toLocaleString()}`, margin, 33);

  if (selectedVersions.length > 0) {
    doc.text(`Guidelines: ${selectedVersions.join(', ')}`, margin, 38);
  }

  y = 52;
  doc.setTextColor(40, 50, 60);

  // ---- Messages ----
  for (const msg of messages) {
    const isAI = msg.role === 'ai';
    const roleLabel = isAI ? '🤖 AI Assistant' : '👤 You';
    const timeStr = msg.timestamp.toLocaleTimeString();
    const lines = doc.splitTextToSize(msg.content, contentW - 8);

    checkPageBreak(20);

    // Role header
    if (isAI) {
      doc.setFillColor(0, 30, 45);
    } else {
      doc.setFillColor(20, 25, 35);
    }
    doc.roundedRect(margin, y, contentW, 8, 2, 2, 'F');

    doc.setTextColor(isAI ? 0 : 200, isAI ? 212 : 210, isAI ? 255 : 230);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'bold');
    doc.text(roleLabel, margin + 4, y + 5.5);

    doc.setTextColor(120, 130, 150);
    doc.setFontSize(7);
    doc.setFont('helvetica', 'normal');
    doc.text(timeStr, pageW - margin - doc.getTextWidth(timeStr) - 4, y + 5.5);

    y += 10;

    // Content
    doc.setTextColor(50, 60, 75);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');

    for (const line of lines) {
      checkPageBreak(6);
      doc.text(line, margin + 4, y);
      y += 5;
    }
    y += 6;
  }

  // ---- Sources ----
  const allSources = messages
    .filter((m) => m.sources && m.sources.length > 0)
    .flatMap((m) => m.sources!);

  if (allSources.length > 0) {
    checkPageBreak(20);
    doc.setDrawColor(0, 212, 255);
    doc.line(margin, y, pageW - margin, y);
    y += 6;

    doc.setTextColor(0, 212, 255);
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.text('Source References', margin, y);
    y += 8;

    const seen = new Set<string>();
    for (const src of allSources) {
      const key = `${src.filename}-${src.page_num}`;
      if (seen.has(key)) continue;
      seen.add(key);
      checkPageBreak(6);
      doc.setTextColor(60, 70, 90);
      doc.setFontSize(8);
      doc.setFont('helvetica', 'normal');
      doc.text(
        `• ${src.filename}${src.page_num ? ` · Page ${src.page_num}` : ''}${src.guideline_version ? ` · ${src.guideline_version}` : ''}`,
        margin + 4,
        y
      );
      y += 5;
    }
  }

  // ---- Footer on all pages ----
  const pageCount = (doc as any).internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFontSize(7);
    doc.setTextColor(120, 130, 150);
    doc.text(`The Compliance Leader — Confidential · Page ${i} of ${pageCount}`, margin, pageH - 6);
  }

  doc.save(`compliance-chat-${new Date().toISOString().split('T')[0]}.pdf`);
}

// ---------------------------------------------------------------------------
// DOCX Export using docx library
// ---------------------------------------------------------------------------

export async function exportAsDOCX({
  messages,
  selectedVersions = [],
  sessionTitle = 'Compliance AI Chat Transcript',
}: ExportOptions): Promise<void> {
  const {
    Document,
    Paragraph,
    TextRun,
    HeadingLevel,
    AlignmentType,
    BorderStyle,
    Packer,
  } = await import('docx');

  const children: any[] = [];

  // Title
  children.push(
    new Paragraph({
      text: 'The Compliance Leader',
      heading: HeadingLevel.HEADING_1,
    }),
    new Paragraph({
      text: sessionTitle,
      heading: HeadingLevel.HEADING_2,
    }),
    new Paragraph({
      children: [
        new TextRun({ text: 'Generated: ', bold: true }),
        new TextRun(new Date().toLocaleString()),
      ],
    })
  );

  if (selectedVersions.length > 0) {
    children.push(
      new Paragraph({
        children: [
          new TextRun({ text: 'Guidelines: ', bold: true }),
          new TextRun(selectedVersions.join(', ')),
        ],
      })
    );
  }

  children.push(new Paragraph({ text: '' }));

  // Messages
  for (const msg of messages) {
    const isAI = msg.role === 'ai';
    const roleLabel = isAI ? '🤖 AI Assistant' : '👤 You';

    children.push(
      new Paragraph({
        children: [
          new TextRun({
            text: `${roleLabel} · ${msg.timestamp.toLocaleTimeString()}`,
            bold: true,
            color: isAI ? '00D4FF' : '7B2FBE',
          }),
        ],
      })
    );

    // Split long content into paragraphs
    const paras = msg.content.split('\n').filter((l) => l.trim());
    for (const para of paras) {
      children.push(
        new Paragraph({
          children: [new TextRun({ text: para })],
        })
      );
    }

    children.push(new Paragraph({ text: '' }));
  }

  // Sources
  const allSources = messages
    .filter((m) => m.sources && m.sources.length > 0)
    .flatMap((m) => m.sources!);

  if (allSources.length > 0) {
    children.push(
      new Paragraph({
        text: 'Source References',
        heading: HeadingLevel.HEADING_3,
      })
    );
    const seen = new Set<string>();
    for (const src of allSources) {
      const key = `${src.filename}-${src.page_num}`;
      if (seen.has(key)) continue;
      seen.add(key);
      children.push(
        new Paragraph({
          children: [
            new TextRun({
              text: `• ${src.filename}${src.page_num ? ` · Page ${src.page_num}` : ''}${src.guideline_version ? ` · ${src.guideline_version}` : ''}`,
            }),
          ],
        })
      );
    }
  }

  const doc = new Document({
    sections: [{ children }],
    creator: 'The Compliance Leader',
    title: sessionTitle,
    description: `Exported chat transcript — ${new Date().toISOString()}`,
  });

  const buffer = await Packer.toBlob(doc);
  const url = URL.createObjectURL(buffer);
  const a = document.createElement('a');
  a.href = url;
  a.download = `compliance-chat-${new Date().toISOString().split('T')[0]}.docx`;
  a.click();
  URL.revokeObjectURL(url);
}
