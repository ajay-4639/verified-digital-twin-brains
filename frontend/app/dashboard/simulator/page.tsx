'use client';

import { SimulatorView } from '@/components/training/SimulatorView';

/**
 * Simulator Page (Legacy/Direct Access)
 * 
 * Now uses the reusable SimulatorView component.
 */
export default function SimulatorPage() {
    return (
        <div className="h-screen bg-[#f8fafc] p-6">
            <SimulatorView />
        </div>
    );
}
