'use client';

import React, { useCallback, useEffect, useState } from 'react';
import ChatInterface from '@/components/Chat/ChatInterface';
import { getSupabaseClient } from '@/lib/supabase/client';

interface ClarificationThread {
    id: string;
    question: string;
    options?: Array<{ label: string; value?: string; stance?: string; intensity?: number }>;
    memory_write_proposal?: { topic?: string; memory_type?: string };
    original_query?: string;
    created_at?: string;
    mode?: string;
    status?: string;
}

interface OwnerMemory {
    id: string;
    topic_normalized: string;
    memory_type: string;
    value: string;
    stance?: string | null;
    intensity?: number | null;
    confidence?: number | null;
    created_at?: string;
}

export function TrainingTab({ twinId }: { twinId: string }) {
    const supabase = getSupabaseClient();
    const [pending, setPending] = useState<ClarificationThread[]>([]);
    const [memories, setMemories] = useState<OwnerMemory[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [answers, setAnswers] = useState<Record<string, { answer: string; selected_option?: string }>>({});

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) {
                setError('Not authenticated.');
                setLoading(false);
                return;
            }

            const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
            const [pendingRes, memoryRes] = await Promise.all([
                fetch(`${backendUrl}/twins/${twinId}/clarifications?status=pending_owner`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                }),
                fetch(`${backendUrl}/twins/${twinId}/owner-memory?status=active`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                })
            ]);

            if (pendingRes.ok) {
                const data = await pendingRes.json();
                setPending(Array.isArray(data) ? data : []);
            } else {
                setPending([]);
            }

            if (memoryRes.ok) {
                const data = await memoryRes.json();
                setMemories(Array.isArray(data) ? data : []);
            } else {
                setMemories([]);
            }
        } catch (err) {
            console.error(err);
            setError('Failed to load training data.');
        } finally {
            setLoading(false);
        }
    }, [supabase, twinId]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const resolveClarification = async (thread: ClarificationThread) => {
        const entry = answers[thread.id];
        const answer = entry?.answer?.trim() || '';
        if (!answer) {
            setError('Please provide a one-sentence answer.');
            return;
        }
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) {
                setError('Not authenticated.');
                return;
            }
            const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
            const res = await fetch(`${backendUrl}/twins/${twinId}/clarifications/${thread.id}/resolve`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    answer,
                    selected_option: entry?.selected_option || undefined
                })
            });
            if (!res.ok) {
                throw new Error(`Resolve failed (${res.status})`);
            }
            setAnswers((prev) => ({ ...prev, [thread.id]: { answer: '', selected_option: undefined } }));
            fetchData();
        } catch (err) {
            console.error(err);
            setError('Failed to resolve clarification.');
        }
    };

    return (
        <div className="p-6 space-y-6">
            {error && (
                <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                    {error}
                </div>
            )}
            <div className="grid lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-6 items-start">
                <div className="min-w-0">
                    <ChatInterface
                        twinId={twinId}
                        mode="training"
                        onMemoryUpdated={fetchData}
                    />
                </div>
                <div className="space-y-6">
                    <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h3 className="text-sm font-semibold text-white">Pending Clarifications</h3>
                                <p className="text-xs text-slate-400">Resolve public or owner questions</p>
                            </div>
                            <button
                                onClick={fetchData}
                                className="text-[10px] uppercase tracking-wider font-bold text-indigo-300 border border-indigo-400/40 px-2 py-1 rounded-lg hover:bg-indigo-500/10"
                            >
                                Refresh
                            </button>
                        </div>
                        {loading ? (
                            <div className="text-xs text-slate-400">Loading...</div>
                        ) : pending.length === 0 ? (
                            <div className="text-xs text-slate-500">No pending clarifications.</div>
                        ) : (
                            <div className="space-y-4">
                                {pending.map((thread) => {
                                    const entry = answers[thread.id] || { answer: '', selected_option: undefined };
                                    return (
                                        <div key={thread.id} className="rounded-xl border border-white/10 bg-black/30 p-3 space-y-3">
                                            <div className="text-xs text-slate-400 uppercase tracking-wider">
                                                {thread.mode === 'public' ? 'Public question' : 'Owner training'}
                                            </div>
                                            <div className="text-sm text-white">{thread.question}</div>
                                            {thread.memory_write_proposal?.topic && (
                                                <div className="text-[10px] text-slate-400">
                                                    Topic: <span className="text-slate-200">{thread.memory_write_proposal.topic}</span> | Type: <span className="text-slate-200">{thread.memory_write_proposal.memory_type}</span>
                                                </div>
                                            )}
                                            {Array.isArray(thread.options) && thread.options.length > 0 && (
                                                <div className="space-y-2">
                                                    {thread.options.map((opt, idx) => (
                                                        <label key={idx} className="flex items-center gap-2 text-xs text-slate-300">
                                                            <input
                                                                type="radio"
                                                                name={`opt-${thread.id}`}
                                                                checked={entry.selected_option === opt.label}
                                                                onChange={() => setAnswers((prev) => ({
                                                                    ...prev,
                                                                    [thread.id]: {
                                                                        answer: opt.value || opt.label,
                                                                        selected_option: opt.label
                                                                    }
                                                                }))}
                                                            />
                                                            <span className="font-semibold">{opt.label}</span>
                                                        </label>
                                                    ))}
                                                </div>
                                            )}
                                            <input
                                                type="text"
                                                value={entry.answer}
                                                onChange={(e) => setAnswers((prev) => ({
                                                    ...prev,
                                                    [thread.id]: {
                                                        answer: e.target.value,
                                                        selected_option: undefined
                                                    }
                                                }))}
                                                placeholder="Answer in one sentence..."
                                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500"
                                            />
                                            <div className="flex justify-end">
                                                <button
                                                    onClick={() => resolveClarification(thread)}
                                                    className="px-3 py-2 text-[10px] uppercase tracking-wider font-bold bg-emerald-500 text-white rounded-lg"
                                                >
                                                    Save Memory
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h3 className="text-sm font-semibold text-white">Owner Memory Log</h3>
                                <p className="text-xs text-slate-400">Active beliefs, preferences, and stance</p>
                            </div>
                            <span className="text-[10px] text-slate-500">{memories.length} items</span>
                        </div>
                        {loading ? (
                            <div className="text-xs text-slate-400">Loading...</div>
                        ) : memories.length === 0 ? (
                            <div className="text-xs text-slate-500">No owner memory yet.</div>
                        ) : (
                            <div className="space-y-3">
                                {memories.slice(0, 20).map((mem) => (
                                    <div key={mem.id} className="rounded-xl border border-white/10 bg-black/20 p-3">
                                        <div className="flex items-center justify-between">
                                            <div className="text-xs font-semibold text-white">{mem.topic_normalized}</div>
                                            <span className="text-[10px] text-slate-400 uppercase tracking-wider">{mem.memory_type}</span>
                                        </div>
                                        <div className="text-xs text-slate-300 mt-2">{mem.value}</div>
                                        <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-slate-400">
                                            {mem.stance && <span>stance: {mem.stance}</span>}
                                            {mem.intensity != null && <span>intensity: {mem.intensity}/10</span>}
                                            {mem.confidence != null && <span>conf: {mem.confidence.toFixed(2)}</span>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default TrainingTab;
