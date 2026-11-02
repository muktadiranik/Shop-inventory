export class RequestError extends Error {
  constructor(message, details = []) {
    super(message);
    this.name = 'RequestError';
    this.details = details;
  }
}

export class ValidationError extends Error {
  constructor(errors) {
    super(errors.map((error) => error.message).join(' '));
    this.name = 'ValidationError';
    this.fieldErrors = errors;
  }
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function validErrors(value) {
  return Array.isArray(value) && value.every((error) => isRecord(error) && typeof error.message === 'string');
}

export async function graphqlRequest(query, variables = {}, { signal } = {}) {
  let response;
  try {
    response = await fetch('/graphql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ query, variables }),
      signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new RequestError('Cannot reach the inventory server. Check that the backend is running and try again.');
  }
  let result;
  try {
    result = await response.json();
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new RequestError(`The server returned an unreadable response (${response.status}).`);
  }
  if (!isRecord(result) || ('errors' in result && !validErrors(result.errors)) || ('data' in result && result.data !== null && !isRecord(result.data))) {
    throw new RequestError('The server returned an invalid GraphQL response. Please try again.');
  }
  if (!response.ok) {
    throw new RequestError(result.errors?.map((error) => error.message).join(' ') || (typeof result.error === 'string' && result.error) || `Server request failed (${response.status}).`, result.errors);
  }
  if (result.errors?.length) {
    throw new RequestError(result.errors.map((error) => error.message).join(' '), result.errors);
  }
  if (!result.data) throw new RequestError('The server returned no inventory data.');
  return result.data;
}

export function mutationValue(data, name) {
  const result = isRecord(data) ? data[name] : null;
  if (!isRecord(result) || !validErrors(result.errors)) throw new RequestError('The server returned an incomplete mutation result.');
  if (result.errors?.length) throw new ValidationError(result.errors);
  if (!isRecord(result.product)) throw new RequestError('The server returned an incomplete mutation result.');
  return result;
}

export function fieldError(error, name) {
  return error?.fieldErrors?.find((item) => item.field === name)?.message;
}
