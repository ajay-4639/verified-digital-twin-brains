'use client';

import React from 'react';
import { useTwin } from '@/lib/context/TwinContext';

export default function SyncStatusBanner() {
    const { syncStatus, syncMessage } = useTwin();

    if (syncStatus === 'idle' || syncStatus === 'ok' || syncStatus === 'syncing') {
        return null;
    }

    return (
        <div className="mb-4 flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 shadow-sm">
            <svg className="h-4 w-4 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4c-.77-1.33-2.69-1.33-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z" />
            </svg>
            <span className="font-medium">{syncMessage || 'Sync temporarily unavailable. Retrying...'}</span>
        </div>
    );
}
