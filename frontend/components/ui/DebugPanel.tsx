'use client';

import { useState } from 'react';
import { API_BASE_URL, API_ENDPOINTS } from '@/lib/constants';
import { useRequestLogger } from '@/lib/hooks/useRequestLogger';

export function DebugPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const { logs, isEnabled, clearLogs, toggleEnabled } = useRequestLogger();
  const [activeTab, setActiveTab] = useState<'requests' | 'config'>('requests');

  // Only show in development
  if (process.env.NODE_ENV !== 'development') return null;

  const getStatusColor = (status?: number) => {
    if (!status) return 'text-gray-500';
    if (status >= 200 && status < 300) return 'text-green-600';
    if (status >= 400) return 'text-red-600';
    return 'text-yellow-600';
  };

  return (
    <>
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-4 left-4 z-50 w-10 h-10 bg-slate-800 text-white rounded-full shadow-lg flex items-center justify-center hover:bg-slate-700 transition-colors"
        title="Debug Panel"
      >
        🐛
      </button>

      {/* Panel */}
      {isOpen && (
        <div className="fixed bottom-16 left-4 z-50 w-[500px] max-h-[600px] bg-white rounded-lg shadow-2xl border border-slate-200 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50 rounded-t-lg">
            <div className="flex items-center gap-4">
              <h3 className="font-semibold text-slate-700">Debug Panel</h3>
              <div className="flex gap-2">
                <button
                  onClick={() => setActiveTab('requests')}
                  className={`px-3 py-1 text-xs rounded ${activeTab === 'requests' ? 'bg-slate-200' : 'hover:bg-slate-100'}`}
                >
                  Requests ({logs.length})
                </button>
                <button
                  onClick={() => setActiveTab('config')}
                  className={`px-3 py-1 text-xs rounded ${activeTab === 'config' ? 'bg-slate-200' : 'hover:bg-slate-100'}`}
                >
                  Config
                </button>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-slate-400 hover:text-slate-600"
            >
              ✕
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-auto p-4">
            {activeTab === 'requests' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={isEnabled}
                      onChange={toggleEnabled}
                    />
                    Log requests
                  </label>
                  {logs.length > 0 && (
                    <button
                      onClick={clearLogs}
                      className="text-xs text-red-600 hover:text-red-800"
                    >
                      Clear logs
                    </button>
                  )}
                </div>

                <div className="space-y-2">
                  {logs.length === 0 ? (
                    <p className="text-sm text-slate-400 text-center py-8">
                      No requests logged yet
                    </p>
                  ) : (
                    logs.map((log) => (
                      <div
                        key={log.id}
                        className="text-xs border border-slate-100 rounded p-2 hover:bg-slate-50"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-mono">{log.method}</span>
                          <span className={`font-bold ${getStatusColor(log.status)}`}>
                            {log.status || 'ERR'}
                          </span>
                          <span className="text-slate-400 ml-auto">
                            {log.duration}ms
                          </span>
                        </div>
                        <div className="text-slate-500 truncate mt-1">
                          {log.url}
                        </div>
                        {log.error && (
                          <div className="text-red-600 mt-1">
                            {log.error}
                          </div>
                        )}
                        <div className="text-slate-300 mt-1">
                          {log.timestamp.toLocaleTimeString()}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {activeTab === 'config' && (
              <div className="space-y-4 text-sm">
                <div>
                  <div className="font-medium text-slate-500 uppercase text-xs tracking-wider mb-1">
                    API Base URL
                  </div>
                  <code className="bg-slate-100 px-2 py-1 rounded block">
                    {API_BASE_URL}
                  </code>
                </div>

                <div>
                  <div className="font-medium text-slate-500 uppercase text-xs tracking-wider mb-1">
                    Environment
                  </div>
                  <div>{process.env.NODE_ENV}</div>
                </div>

                <div>
                  <div className="font-medium text-slate-500 uppercase text-xs tracking-wider mb-2">
                    Available Endpoints
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <a
                      href={`${API_BASE_URL}/docs`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      /docs (Swagger)
                    </a>
                    <a
                      href={`${API_BASE_URL}/health`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      /health
                    </a>
                    <a
                      href={`${API_BASE_URL}/version`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      /version
                    </a>
                    <a
                      href={`${API_BASE_URL}/cors-test`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      /cors-test
                    </a>
                  </div>
                </div>

                <div>
                  <div className="font-medium text-slate-500 uppercase text-xs tracking-wider mb-2">
                    Quick Tests
                  </div>
                  <div className="space-y-2">
                    <button
                      onClick={async () => {
                        const res = await fetch(`${API_BASE_URL}/health`);
                        alert(`Health check: ${res.status}`);
                      }}
                      className="w-full text-left px-3 py-2 bg-slate-50 hover:bg-slate-100 rounded text-xs"
                    >
                      Test /health endpoint
                    </button>
                    <button
                      onClick={async () => {
                        const res = await fetch(`${API_BASE_URL}/version`);
                        const data = await res.json();
                        alert(`Version: ${data.git_sha}\nEnvironment: ${data.environment}`);
                      }}
                      className="w-full text-left px-3 py-2 bg-slate-50 hover:bg-slate-100 rounded text-xs"
                    >
                      Test /version endpoint
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
