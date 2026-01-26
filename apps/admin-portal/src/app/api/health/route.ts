import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    service: 'admin-portal',
    timestamp: new Date().toISOString(),
  });
}
