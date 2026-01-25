'use client';

import { useState, useEffect } from 'react';
import { useRealtimeInterview, TranscriptTurn } from '@/lib/hooks/useRealtimeInterview';

/**
 * Interview Mode Page
 * 
 * Real-time voice interview for capturing user intent, goals, constraints,
 * preferences, and boundaries into the temporal knowledge graph.
 */
export default function InterviewPage() {
    const {
        isConnected,
        isRecording,
        error,
        transcript,
        connectionStatus,
        startInterview,
        stopInterview,
        clearTranscript,
    } = useRealtimeInterview({
        onTranscriptUpdate: (updated) => {
            console.log('Transcript updated:', updated.length, 'turns');
        },
        onError: (err) => {
            console.error('Interview error:', err);
        },
    });

    const [duration, setDuration] = useState(0);

    // Timer for interview duration
    useEffect(() => {
        let interval: NodeJS.Timeout | null = null;
        if (isRecording) {
            interval = setInterval(() => {
                setDuration((d) => d + 1);
            }, 1000);
        } else {
            setDuration(0);
        }
        return () => {
            if (interval) clearInterval(interval);
        };
    }, [isRecording]);

    const formatDuration = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };

    const getStatusColor = () => {
        switch (connectionStatus) {
            case 'connected':
                return 'bg-green-500';
            case 'connecting':
                return 'bg-yellow-500';
            case 'error':
                return 'bg-red-500';
            default:
                return 'bg-gray-400';
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
            <div className="max-w-4xl mx-auto px-4 py-8">
                {/* Header */}
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-bold text-white mb-2">
                        Interview Mode
                    </h1>
                    <p className="text-slate-400">
                        Tell me about yourself — your goals, preferences, and what matters to you.
                    </p>
                </div>

                {/* Connection Status */}
                <div className="flex items-center justify-center gap-2 mb-6">
                    <div className={`w-3 h-3 rounded-full ${getStatusColor()} animate-pulse`} />
                    <span className="text-slate-300 text-sm capitalize">
                        {connectionStatus}
                    </span>
                    {isRecording && (
                        <span className="text-slate-400 text-sm ml-4">
                            {formatDuration(duration)}
                        </span>
                    )}
                </div>

                {/* Error Display */}
                {error && (
                    <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                        <p className="text-red-400 text-sm">{error}</p>
                    </div>
                )}

                {/* Main Control */}
                <div className="flex flex-col items-center mb-8">
                    <button
                        onClick={isRecording ? stopInterview : startInterview}
                        disabled={connectionStatus === 'connecting'}
                        className={`
              w-24 h-24 rounded-full flex items-center justify-center
              transition-all duration-300 transform hover:scale-105
              ${isRecording
                                ? 'bg-red-500 hover:bg-red-600 shadow-lg shadow-red-500/30'
                                : 'bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 shadow-lg shadow-purple-500/30'
                            }
              ${connectionStatus === 'connecting' ? 'opacity-50 cursor-not-allowed' : ''}
            `}
                    >
                        {connectionStatus === 'connecting' ? (
                            <svg className="w-8 h-8 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                        ) : isRecording ? (
                            <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                                <rect x="6" y="6" width="12" height="12" rx="2" />
                            </svg>
                        ) : (
                            <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                            </svg>
                        )}
                    </button>

                    <p className="mt-4 text-slate-400 text-sm">
                        {connectionStatus === 'connecting'
                            ? 'Connecting...'
                            : isRecording
                                ? 'Click to stop'
                                : 'Click to start interview'
                        }
                    </p>
                </div>

                {/* Transcript Panel */}
                <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50">
                        <h2 className="text-white font-medium">Transcript</h2>
                        {transcript.length > 0 && (
                            <button
                                onClick={clearTranscript}
                                className="text-slate-400 hover:text-white text-sm transition-colors"
                            >
                                Clear
                            </button>
                        )}
                    </div>

                    <div className="p-4 min-h-[300px] max-h-[400px] overflow-y-auto">
                        {transcript.length === 0 ? (
                            <div className="flex items-center justify-center h-full min-h-[200px]">
                                <p className="text-slate-500 text-sm">
                                    {isRecording
                                        ? 'Listening... Start speaking.'
                                        : 'Start the interview to see the transcript here.'
                                    }
                                </p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {transcript.map((turn, index) => (
                                    <TranscriptItem key={index} turn={turn} />
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Instructions */}
                <div className="mt-8 p-4 bg-slate-800/30 rounded-lg border border-slate-700/30">
                    <h3 className="text-white font-medium mb-2">Tips for a great interview</h3>
                    <ul className="text-slate-400 text-sm space-y-1">
                        <li>• Speak naturally about what you&apos;re trying to accomplish</li>
                        <li>• Share your goals, both short and long-term</li>
                        <li>• Mention any constraints or limitations you face</li>
                        <li>• Express your preferences and how you like to work</li>
                        <li>• Let me know about any boundaries or topics to avoid</li>
                    </ul>
                </div>
            </div>
        </div>
    );
}

function TranscriptItem({ turn }: { turn: TranscriptTurn }) {
    const isUser = turn.role === 'user';

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div
                className={`
          max-w-[80%] px-4 py-2 rounded-2xl
          ${isUser
                        ? 'bg-blue-600 text-white rounded-br-md'
                        : 'bg-slate-700 text-slate-100 rounded-bl-md'
                    }
        `}
            >
                <p className="text-sm">{turn.content}</p>
                <p className={`text-xs mt-1 ${isUser ? 'text-blue-200' : 'text-slate-400'}`}>
                    {new Date(turn.timestamp).toLocaleTimeString()}
                </p>
            </div>
        </div>
    );
}
