import { format, formatDistanceToNow } from 'date-fns';

export function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return format(date, 'MMM d, yyyy');
  } catch {
    return dateString;
  }
}

export function formatDateTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    return format(date, 'MMM d, yyyy • h:mm a');
  } catch {
    return dateString;
  }
}

export function formatRelative(dateString: string): string {
  try {
    const date = new Date(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return dateString;
  }
}

export function shortHash(hash: string, length: number = 8): string {
  if (hash.length <= length * 2) return hash;
  return `${hash.slice(0, length)}...${hash.slice(-4)}`;
}

export function fullHash(hash: string): string {
  return hash;
}
