'use client';

import React, { useState, useRef, useEffect } from 'react';
import ChatInterface from '../../components/Chat/ChatInterface';
import Link from 'next/link';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const AUTH_TOKEN = process.env.NEXT_PUBLIC_DEV_TOKEN || 'development_token';

export default function DashboardPage() {
  const [activeTwin, setActiveTwin] = useState('eeeed554-9180-4229-a9af-0f8dd2c69e9b');
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [systemStatus, setSystemStatus] = useState<'checking' | 'online' | 'offline' | 'degraded'>('checking');
  const [sources, setSources] = useState<any[]>([]);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch sources
  const fetchSources = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/sources/${activeTwin}`, {
        headers: { 'Authorization': `Bearer ${AUTH_TOKEN}` }
      });
      if (response.ok) {
        const data = await response.json();
        setSources(data);
      }
    } catch (error) {
      console.error('Error fetching sources:', error);
    }
  };

  const handleDeleteSource = async (sourceId: string) => {
    if (!confirm('Are you sure you want to delete this source? This will remove it from your twin\'s memory.')) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/sources/${activeTwin}/${sourceId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${AUTH_TOKEN}` }
      });
      if (response.ok) {
        await fetchSources();
      } else {
        alert('Failed to delete source.');
      }
    } catch (error) {
      console.error('Error deleting source:', error);
      alert('Error connecting to backend.');
    }
  };

  // Check system health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
          const data = await response.json();
          setSystemStatus(data.status === 'online' ? 'online' : 'degraded');
        } else {
          setSystemStatus('offline');
        }
      } catch (error) {
        setSystemStatus('offline');
      }
    };
    checkHealth();
    fetchSources();
    const interval = setInterval(checkHealth, 10000); // Check every 10s
    return () => clearInterval(interval);
  }, [activeTwin]);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE_URL}/ingest/${activeTwin}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${AUTH_TOKEN}`, // Using dev token for local testing
        },
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        await fetchSources(); // Refresh sources list
        alert(`Successfully ingested ${data.chunks_ingested} chunks from ${file.name}`);
      } else {
        const error = await response.json();
        alert(`Upload failed: ${error.detail || 'Server error'}`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('Failed to connect to backend. Is the FastAPI server running on port 8000?');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const startNewSession = () => {
    setCurrentConversationId(null);
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#f8fafc] text-slate-900 font-sans">
      <header className="sticky top-0 z-10 bg-white border-b px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/" className="text-xl font-black tracking-tighter text-blue-600 hover:opacity-80 transition-opacity">
            VT-BRAIN
          </Link>
          <nav className="hidden md:flex items-center gap-6">
            <Link href="/dashboard" className="text-sm font-bold text-blue-600 border-b-2 border-blue-600 pb-1">Chat</Link>
            <a href="#" className="text-sm font-medium text-slate-500 hover:text-slate-800">Knowledge Base</a>
            <Link href="/dashboard/escalations" className="text-sm font-medium text-slate-500 hover:text-slate-800">Escalations</Link>
            <Link href="/dashboard/settings" className="text-sm font-medium text-slate-500 hover:text-slate-800">Settings</Link>
            <a href="#" className="text-sm font-medium text-slate-500 hover:text-slate-800">Analytics</a>
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full border bg-slate-50">
            <span className={`w-2 h-2 rounded-full ${
              systemStatus === 'online' ? 'bg-green-500' : 
              systemStatus === 'degraded' ? 'bg-yellow-500' : 
              systemStatus === 'offline' ? 'bg-red-500' : 'bg-slate-300'
            }`}></span>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              System: {systemStatus}
            </span>
          </div>
          <div className="flex -space-x-2 overflow-hidden">
            <div className="inline-block h-8 w-8 rounded-full ring-2 ring-white bg-slate-200 flex items-center justify-center text-[10px] font-bold">JD</div>
          </div>
          <button className="text-xs font-bold text-slate-400 hover:text-slate-600 uppercase tracking-widest transition-colors">Logout</button>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full p-6 md:p-10 grid grid-cols-1 lg:grid-cols-4 gap-8">
        <div className="lg:col-span-3 h-[750px] flex flex-col">
          <div className="mb-6 flex items-center justify-between">
            <h1 className="text-2xl font-extrabold tracking-tight">AI Assistant</h1>
            <div className="flex gap-2">
              <button 
                onClick={startNewSession}
                className="bg-white border text-xs font-bold px-4 py-2 rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
              >
                New Session
              </button>
              <button className="bg-blue-600 text-white text-xs font-bold px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors shadow-sm">Manage Twin</button>
            </div>
          </div>
          <div className="flex-1 shadow-2xl rounded-2xl overflow-hidden">
            <ChatInterface 
              twinId={activeTwin} 
              conversationId={currentConversationId} 
              onConversationStarted={setCurrentConversationId}
            />
          </div>
        </div>

        <div className="lg:col-span-1 space-y-8">
          <section className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
            <h2 className="text-sm font-black text-slate-400 uppercase tracking-widest mb-4">Active Knowledge</h2>
            <div className="space-y-3">
              {sources.map((doc, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors cursor-pointer group border border-transparent hover:border-slate-200">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path></svg>
                    </div>
                    <div className="overflow-hidden">
                      <div className="text-xs font-bold text-slate-700 truncate">{doc.filename}</div>
                      <div className="text-[10px] text-slate-400 font-medium">
                        {new Date(doc.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full ${doc.status === 'processed' ? 'bg-green-500' : 'bg-yellow-500'}`}></span>
                    <button 
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSource(doc.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 text-slate-400 hover:text-red-500 rounded-md transition-all"
                      title="Delete Source"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </button>
                  </div>
                </div>
              ))}
              
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileChange} 
                className="hidden" 
                accept=".pdf"
              />
              
              <button 
                onClick={handleUploadClick}
                disabled={isUploading}
                className={`w-full mt-2 py-3 border-2 border-dashed rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
                  isUploading 
                  ? 'bg-slate-50 border-blue-200 text-blue-400 cursor-not-allowed' 
                  : 'border-slate-200 text-slate-400 hover:border-blue-400 hover:text-blue-500'
                }`}
              >
                {isUploading ? (
                  <>
                    <svg className="animate-spin h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    Uploading...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
                    Add Source (PDF)
                  </>
                )}
              </button>
            </div>
          </section>

          <section className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
            <h2 className="text-sm font-black text-slate-400 uppercase tracking-widest mb-4">Quick Insights</h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-green-50 rounded-xl border border-green-100">
                <div className="text-[10px] font-bold text-green-700 uppercase tracking-wide">Reliability</div>
                <div className="text-xl font-black text-green-800 mt-1">98%</div>
              </div>
              <div className="p-4 bg-indigo-50 rounded-xl border border-indigo-100">
                <div className="text-[10px] font-bold text-indigo-700 uppercase tracking-wide">Sync Time</div>
                <div className="text-xl font-black text-indigo-800 mt-1">2m</div>
              </div>
            </div>
          </section>

          <div className="p-6 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl text-white shadow-lg shadow-blue-200">
            <h3 className="text-sm font-bold mb-2 flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              Did you know?
            </h3>
            <p className="text-xs text-blue-100 leading-relaxed opacity-90">
              The Digital Twin Brain monitors its own confidence. If it drops below 70%, it automatically creates an escalation for you to review.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
