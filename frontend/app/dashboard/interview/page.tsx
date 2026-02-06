'use client';

import { InterviewView } from '@/components/training/InterviewView';

/**
 * Interview Mode Page (Legacy/Direct Access)
 * 
 * Now uses the reusable InterviewView component.
 */
export default function InterviewPage() {
    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8">
            <div className="max-w-4xl mx-auto">
                <InterviewView />
            </div>
        </div>
    );
}
