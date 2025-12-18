function templateSubject(contact) {
  // Customize as needed
  return 'Short quote/anecdote request';
}

function templateBody(contact) {
  // Customize as needed; drafts only, never auto-send
  const rawName = String(contact.name || '').trim();
  // If no name provided or the name is the literal "Email", use a generic salutation.
  let greeting;
  if (!rawName || rawName.toLowerCase() === 'email') {
    greeting = 'Dear Professor,';
  } else {
    greeting = `Dear Professor ${rawName},`;
  }
  const lines = [
    greeting,
    '',
    `I'm a student at the University of Pennsylvania working on a small project for my Legal Practices class collecting brief quotes and anecdotes from esteemed law professors.`,
  ];

  if (contact.affiliation) {
    lines.push(`If you're willing, could you share some knowledge or a story from your time at ${contact.affiliation}?`);
  } else {
    lines.push(`If you're willing, could you share something you learned from your time teaching?`);
  }

  if (contact.subject) {
    lines.push(`(Anything related to ${contact.subject} is great.)`);
  }

  lines.push(
    '',
    `Thank you,`,
    `Shane Murphy`,
  );

  return lines.join('\n');
}

function createDrafts() {
  const sheetName = 'law_contacts';
  const statusColName = 'DraftStatus';
  const sentSheetName = 'SentLog';
  const ss = SpreadsheetApp.getActive();
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    SpreadsheetApp.getUi().alert(`Sheet '${sheetName}' not found.`);
    return;
  }

  const range = sheet.getDataRange();
  const values = range.getValues();
  if (values.length < 2) {
    SpreadsheetApp.getUi().alert('No data rows found.');
    return;
  }

  const headers = values[0].map(h => String(h).trim());
  const idx = {
    subject: headers.indexOf('subject'),
    subject_alt: headers.indexOf('area_of_law'),
    subject_alt2: headers.indexOf('area'),
    name: headers.indexOf('name'),
    email: headers.indexOf('email'),
    affiliation: headers.indexOf('affiliation'),
    source_url: headers.indexOf('source_url'),
  };
  if (idx.email === -1) {
    SpreadsheetApp.getUi().alert("Missing required 'email' column in the first row header.");
    return;
  }
  let statusIdx = headers.indexOf(statusColName);
  if (statusIdx === -1) {
    // Add a DraftStatus column if missing
    sheet.insertColumnAfter(headers.length);
    statusIdx = headers.length; // zero-based in array but 1-based in sheet ops
    sheet.getRange(1, statusIdx + 1).setValue(statusColName);
  }

  // Prepare SentLog and set of already-sent emails
  const sentSheet = ensureSheetWithHeaders(ss, sentSheetName, ['email', 'sent_at']);
  let existingSent = [];
  const sentLastRow = sentSheet.getLastRow();
  if (sentLastRow >= 2) {
    existingSent = sentSheet.getRange(2, 1, sentLastRow - 1, 1).getValues();
  }
  const sentSet = new Set(
    existingSent
      .map(r => String(r[0] || '').trim().toLowerCase())
      .filter(e => !!e)
  );

  let created = 0;
  for (let r = 1; r < values.length; r++) {
    const row = values[r];
    const email = idx.email >= 0 ? String(row[idx.email] || '').trim() : '';
    if (!email) continue;
    if (sentSet.has(email.toLowerCase())) {
      // Already sent—skip creating draft
      continue;
    }
    const status = String(row[statusIdx] || '').trim();
    if (status) continue; // Skip rows already marked

    const contact = {
      name: idx.name >= 0 ? String(row[idx.name] || '').trim() : '',
      email,
      affiliation: idx.affiliation >= 0 ? String(row[idx.affiliation] || '').trim() : '',
      source_url: idx.source_url >= 0 ? String(row[idx.source_url] || '').trim() : '',
      subject: (idx.subject >= 0 ? String(row[idx.subject] || '').trim() : '') ||
               (idx.subject_alt >= 0 ? String(row[idx.subject_alt] || '').trim() : '') ||
               (idx.subject_alt2 >= 0 ? String(row[idx.subject_alt2] || '').trim() : ''),
    };

    const subject = templateSubject(contact);
    const body = templateBody(contact);
    GmailApp.createDraft(contact.email, subject, body);
    sheet.getRange(r + 1, statusIdx + 1).setValue(`Created ${new Date().toISOString()}`);
    created++;
  }

  SpreadsheetApp.getUi().alert(`Created ${created} drafts.`);
}

function sendFirstDraftsPrompt() {
  const ui = SpreadsheetApp.getUi();
  const num = ui.prompt('Send Drafts', 'How many drafts to send?', ui.ButtonSet.OK_CANCEL);
  if (num.getSelectedButton() !== ui.Button.OK) return;
  const limit = parseInt(num.getResponseText(), 10);
  if (!limit || limit < 1) {
    ui.alert('Please enter a positive integer.');
    return;
  }
  const pref = ui.prompt('Subject filter (optional)', 'Only send drafts whose subject starts with this first word (leave blank for all):', ui.ButtonSet.OK_CANCEL);
  if (pref.getSelectedButton() === ui.Button.CANCEL) return;
  const firstWord = String(pref.getResponseText() || '').trim();
  sendFirstDrafts(limit, firstWord);
}

function sendFirstDrafts(limit, subjectFirstWord) {
  const ss = SpreadsheetApp.getActive();
  const sentSheet = ensureSheetWithHeaders(ss, 'SentLog', ['email', 'sent_at']);
  const drafts = GmailApp.getDrafts();
  const wantFirst = String(subjectFirstWord || '').toLowerCase().trim();
  let sent = 0;
  for (let i = 0; i < drafts.length && sent < limit; i++) {
    const d = drafts[i];
    const msg = d.getMessage();
    const subj = String(msg.getSubject() || '').toLowerCase().trim();
    if (wantFirst) {
      const subjFirst = (subj.split(/\s+/)[0] || '');
      if (subjFirst !== wantFirst) continue;
    }
    // Send the draft
    d.send();
    sent++;
    // Log recipients to SentLog
    const toStr = String(msg.getTo() || '');
    const recipients = toStr.split(/[;,]+|\s{2,}/).map(s => s.trim()).filter(Boolean);
    const now = new Date().toISOString();
    if (recipients.length) {
      const start = Math.max(sentSheet.getLastRow() + 1, 2);
      sentSheet.getRange(start, 1, recipients.length, 2).setValues(recipients.map(e => [e, now]));
    }
  }
  SpreadsheetApp.getUi().alert(`Sent ${sent} draft(s).`);
}

function markSelectedAsSent() {
  const sheetName = 'LawContacts';
  const sentSheetName = 'SentLog';
  const ss = SpreadsheetApp.getActive();
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    SpreadsheetApp.getUi().alert(`Sheet '${sheetName}' not found.`);
    return;
  }
  const range = sheet.getActiveRange();
  if (!range) {
    SpreadsheetApp.getUi().alert('Select the rows to mark as sent.');
    return;
  }
  const values = sheet.getDataRange().getValues();
  if (values.length < 2) return;
  const headers = values[0].map(h => String(h).trim());
  const emailIdx = headers.indexOf('email');
  if (emailIdx === -1) {
    SpreadsheetApp.getUi().alert("Missing required 'email' column in the first row header.");
    return;
  }

  const sentSheet = ensureSheetWithHeaders(ss, sentSheetName, ['email', 'sent_at']);
  const sentLast = sentSheet.getLastRow();
  let writeRow = Math.max(sentLast + 1, 2);
  const now = new Date().toISOString();
  const numRows = range.getNumRows();
  const startRow = range.getRow();

  for (let i = 0; i < numRows; i++) {
    const rowIdx = startRow + i;
    if (rowIdx === 1) continue; // skip header
    const email = String(sheet.getRange(rowIdx, emailIdx + 1).getValue() || '').trim();
    if (!email) continue;
    sentSheet.getRange(writeRow, 1, 1, 2).setValues([[email, now]]);
    writeRow++;
  }
  SpreadsheetApp.getUi().alert('Selected rows marked as sent in SentLog.');
}

function ensureSheetWithHeaders(ss, name, headers) {
  let sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.getRange(1, 1, 1, headers.length).setValues([headers]);
  } else if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, headers.length).setValues([headers]);
  }
  return sh;
}

function sendToLabelRecipients() {
  const labelName = 'followup_law';
  const bodyText = ['Thank you for responding, I am a student at the University of Pennsylvania, and it is for a project in my Legal Practices.',
  '',
  '-Shane Murphy' ].join('\n'); // Customize

  const label = GmailApp.getUserLabelByName(labelName);
  if (!label) {
    SpreadsheetApp.getUi().alert(`Label '${labelName}' not found.`);
    return;
  }

  const threads = label.getThreads();
  let replyCount = 0;

  const userEmail = Session.getActiveUser().getEmail();

  for (const thread of threads) {
    const messages = thread.getMessages();
    if (messages.length === 0) continue;

    // Find the last message from someone else
    let lastRecipientMessage = null;
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.getFrom().indexOf(userEmail) === -1) {
        lastRecipientMessage = msg;
        break;
      }
    }

    if (!lastRecipientMessage) continue; // No message from recipient

    // Reply to the last recipient's message, excluding self
    const to = lastRecipientMessage.getFrom();
    const cc = lastRecipientMessage.getCc().split(',').filter(email => email.trim() !== userEmail).join(',');
    const bcc = lastRecipientMessage.getBcc().split(',').filter(email => email.trim() !== userEmail).join(',');

    thread.reply(bodyText, {
      cc: cc || undefined,
      bcc: bcc || undefined
    });
    replyCount++;
  }

  SpreadsheetApp.getUi().alert(`Created ${replyCount} follow-up reply drafts.`);
}


function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('LawQuoteCollector')
    .addItem('Create Drafts', 'createDrafts')
    .addItem('Send to Label Recipients', 'sendToLabelRecipients')
    .addItem('Mark Selected as Sent', 'markSelectedAsSent')
    .addToUi();
}


