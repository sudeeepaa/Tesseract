import React from 'react';
import { FileText } from 'lucide-react';

interface SourceBadgeProps {
  meetingId: string;
}

/** meeting_01 → "Meeting 1"; otherwise Title Case the id. */
export function meetingLabel(meetingId: string): string {
  const m = meetingId.match(/^meeting[_-]?0*(\d+)$/i);
  if (m) return `Meeting ${m[1]}`;
  return meetingId.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export const SourceBadge: React.FC<SourceBadgeProps> = ({ meetingId }) => (
  <span className="source-chip" title={`From ${meetingId}`}>
    <FileText size={12} />
    {meetingLabel(meetingId)}
  </span>
);
