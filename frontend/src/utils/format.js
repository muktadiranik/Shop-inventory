export const MAX_INT = 2147483647;

export function parseInteger(value, field, minimum = 0) {
  const text = String(value).trim();
  const number = Number(text);
  if (!/^\d+$/.test(text) || !Number.isSafeInteger(number) || number < minimum || number > MAX_INT) {
    const error = new Error(`Enter a whole number between ${minimum} and ${MAX_INT}.`);
    error.fieldErrors = [{ field, message: error.message }];
    throw error;
  }
  return number;
}

export function parsePrice(value) {
  const text = String(value).trim();
  if (!/^\d{1,10}(?:\.\d{1,2})?$/.test(text)) {
    const error = new Error('Enter a nonnegative price with at most two decimal places.');
    error.fieldErrors = [{ field: 'unitPriceMinor', message: error.message }];
    throw error;
  }
  const [whole, fraction = ''] = text.split('.');
  const minor = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  if (minor > BigInt(MAX_INT)) {
    const error = new Error('Price cannot exceed 21,474,836.47.');
    error.fieldErrors = [{ field: 'unitPriceMinor', message: error.message }];
    throw error;
  }
  return Number(minor);
}

export function priceInput(minor) {
  return `${Math.floor(minor / 100)}.${String(minor % 100).padStart(2, '0')}`;
}

export function money(minor) {
  return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(minor / 100);
}

export function units(value) {
  return BigInt(value).toLocaleString();
}

export function timestamp(value) {
  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export function downloadCsv(file) {
  const url = URL.createObjectURL(new Blob(['\uFEFF', file.content], { type: file.contentType }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = file.filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
