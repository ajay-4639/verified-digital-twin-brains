'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useTwin } from '@/lib/context/TwinContext';
import { getSupabaseClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Source {
  id: string;
  filename: string;
  file_size: number;
  status: string;
  created_at: string;
  groups?: Array<{ id: string; name: string }>;
}

interface KnowledgeProfile {
  total_chunks: number;
  total_sources: number;
  fact_count: number;
  opinion_count: number;
  tone_distribution: Record<string, number>;
  top_tone: string;
}

const KnowledgeInsights = ({ profile }: { profile: KnowledgeProfile | null }) => {
  if (!profile) return null;

  const total = profile.fact_count + profile.opinion_count;
  const factPercent = total > 0 ? Math.round((profile.fact_count / total) * 100) : 0;
  const opinionPercent = total > 0 ? Math.round((profile.opinion_count / total) * 100) : 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
      {/* Cognitive Balance Card */}
      <div className="bg-gradient-to-br from-indigo-600 to-purple-700 p-8 rounded-3xl text-white shadow-lg shadow-indigo-200">
        <h4 className="text-xs font-black opacity-70 uppercase tracking-widest">Cognitive Balance</h4>
        <div className="mt-6 flex items-end justify-between">
          <div>
            <span className="text-4xl font-black">{opinionPercent}%</span>
            <p className="text-[10px] font-bold opacity-70 mt-1 uppercase">Personality / Opinions</p>
          </div>
          <div className="text-right">
            <span className="text-2xl font-bold opacity-80">{factPercent}%</span>
            <p className="text-[10px] font-bold opacity-70 mt-1 uppercase">Factual Data</p>
          </div>
        </div>
        <div className="mt-6 h-2 w-full bg-white/20 rounded-full overflow-hidden">
          <div
            className="h-full bg-white transition-all duration-1000 ease-out"
            style={{ width: `${opinionPercent}%` }}
          ></div>
        </div>
        <p className="text-[10px] mt-4 opacity-60 font-medium">Your twin is {opinionPercent > factPercent ? 'more opinionated' : 'more factual'}.</p>
      </div>

      {/* Tone Profile Card */}
      <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm">
        <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest">Dominant Tone</h4>
        <div className="mt-6 flex items-center gap-3">
          <span className="text-3xl font-black text-slate-800 tracking-tight">{profile.top_tone}</span>
          <span className="px-2 py-1 bg-green-100 text-green-700 text-[10px] font-black rounded-lg">ACTIVE</span>
        </div>
        <p className="text-xs text-slate-500 mt-4 leading-relaxed font-medium">
          Most of your knowledge sounds <span className="text-slate-900 font-bold">{profile.top_tone.toLowerCase()}</span>.
          The twin will prioritize this style in its responses.
        </p>
      </div>

      {/* Memory Depth Card */}
      <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm">
        <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest">Memory Units</h4>
        <div className="mt-6">
          <span className="text-4xl font-black text-slate-800 tracking-tight">{profile.total_chunks}</span>
          <span className="ml-2 text-xs font-bold text-slate-400">Chunks</span>
        </div>
        <p className="text-xs text-slate-500 mt-4 leading-relaxed font-medium">
          Across <span className="text-slate-900 font-bold">{profile.total_sources}</span> distinct sources,
          your twin has processed {profile.total_chunks} memory segments.
        </p>
      </div>
    </div>
  );
};

export default function KnowledgePage() {
  const { activeTwin, isLoading: twinLoading } = useTwin();
  const supabase = getSupabaseClient();
  const [sources, setSources] = useState<Source[]>([]);
  const [profile, setProfile] = useState<KnowledgeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [podcastUrl, setPodcastUrl] = useState('');
  const [xUrl, setXUrl] = useState('');
  const [ingestingYoutube, setIngestingYoutube] = useState(false);
  const [ingestingPodcast, setIngestingPodcast] = useState(false);
  const [ingestingX, setIngestingX] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const twinId = activeTwin?.id;

  // Get auth token helper
  const getAuthToken = useCallback(async () => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token;
  }, [supabase]);

  const fetchData = useCallback(async () => {
    if (!twinId) return;
    const token = await getAuthToken();
    if (!token) return;
    try {
      const [sourcesRes, profileRes] = await Promise.all([
        fetch(`${API_BASE_URL}/sources/${twinId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch(`${API_BASE_URL}/twins/${twinId}/knowledge-profile`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ]);

      if (sourcesRes.ok) setSources(await sourcesRes.json());
      if (profileRes.ok) setProfile(await profileRes.json());

    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  }, [twinId, getAuthToken]);

  useEffect(() => {
    if (twinId) {
      fetchData();
    }
  }, [twinId, fetchData]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !twinId) return;

    setUploading(true);
    setError(null);
    const token = await getAuthToken();
    if (!token) {
      setError('Not authenticated');
      setUploading(false);
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE_URL}/ingest/file/${twinId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });

      if (response.ok) {
        fetchData();
      } else {
        const data = await response.json();
        setError(data.detail || 'Upload failed');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setUploading(false);
    }
  };

  const handleYoutubeIngest = async () => {
    if (!youtubeUrl.trim() || !twinId) return;

    setIngestingYoutube(true);
    setError(null);
    const token = await getAuthToken();
    if (!token) {
      setError('Not authenticated');
      setIngestingYoutube(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/ingest/youtube/${twinId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url: youtubeUrl }),
      });

      if (response.ok) {
        setYoutubeUrl('');
        fetchData();
      } else {
        const data = await response.json();
        setError(data.detail || 'Ingestion failed');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setIngestingYoutube(false);
    }
  };

  const handlePodcastIngest = async () => {
    if (!podcastUrl.trim() || !twinId) return;

    setIngestingPodcast(true);
    setError(null);
    const token = await getAuthToken();
    if (!token) {
      setError('Not authenticated');
      setIngestingPodcast(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/ingest/podcast/${twinId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url: podcastUrl }),
      });

      if (response.ok) {
        setPodcastUrl('');
        fetchData();
      } else {
        const data = await response.json();
        setError(data.detail || 'Ingestion failed');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setIngestingPodcast(false);
    }
  };

  const handleXIngest = async () => {
    if (!xUrl.trim() || !twinId) return;

    setIngestingX(true);
    setError(null);
    const token = await getAuthToken();
    if (!token) {
      setError('Not authenticated');
      setIngestingX(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/ingest/x/${twinId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url: xUrl }),
      });

      if (response.ok) {
        setXUrl('');
        fetchData();
      } else {
        const data = await response.json();
        setError(data.detail || 'Ingestion failed');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setIngestingX(false);
    }
  };

  const handleDelete = async (sourceId: string) => {
    if (!twinId) return;
    const token = await getAuthToken();
    if (!token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/sources/${twinId}/${sourceId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        setSources(sources.filter(s => s.id !== sourceId));
        // Refresh profile stats after deletion
        const profileRes = await fetch(`${API_BASE_URL}/twins/${twinId}/knowledge-profile`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (profileRes.ok) setProfile(await profileRes.json());
      }
    } catch (error) {
      console.error('Error deleting source:', error);
    }
  };

  // Loading state
  if (twinLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-500">Loading your twin...</p>
        </div>
      </div>
    );
  }

  // No twin state
  if (!twinId) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center max-w-md p-8">
          <div className="w-16 h-16 bg-indigo-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <svg className="w-8 h-8 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-slate-900 mb-3">No Twin Found</h2>
          <p className="text-slate-500 mb-6">
            Create a digital twin first to upload knowledge sources.
          </p>
          <a
            href="/dashboard/right-brain"
            className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors"
          >
            Create Your Twin
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-10 pb-20">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-black tracking-tight text-slate-900">Left Brain</h1>
          <p className="text-slate-500 mt-2 font-medium">Quantify the raw knowledge (Sources) that powers your Digital Twin.</p>
        </div>
        <a
          href="/dashboard/knowledge/staging"
          className="px-6 py-3 bg-indigo-600 text-white rounded-2xl text-sm font-black hover:bg-indigo-700 transition-all"
        >
          View Staging
        </a>
      </div>

      {!loading && <KnowledgeInsights profile={profile} />}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Upload Card */}
        <div className="bg-white p-10 rounded-[2.5rem] border border-slate-200 shadow-sm hover:shadow-xl transition-all duration-300">
          <div className="w-14 h-14 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mb-8">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
          </div>
          <h3 className="text-xl font-black text-slate-800 mb-2">Upload Documents</h3>
          <p className="text-sm text-slate-500 mb-8 font-medium leading-relaxed">Upload PDFs, Audio files, or Text documents to enrich your twin's knowledge base.</p>

          <label className="block">
            <span className="sr-only">Choose file</span>
            <input
              type="file"
              onChange={handleFileUpload}
              disabled={uploading}
              className="block w-full text-sm text-slate-500 file:mr-6 file:py-3 file:px-6 file:rounded-2xl file:border-0 file:text-sm file:font-black file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer disabled:opacity-50 transition-all"
            />
          </label>
          {uploading && <div className="mt-6 text-xs font-black text-blue-600 animate-pulse flex items-center gap-3">
            <div className="w-2.5 h-2.5 bg-blue-600 rounded-full animate-bounce"></div> Ingesting and embedding...
          </div>}
        </div>

        {/* YouTube Card */}
        <div className="bg-white p-10 rounded-[2.5rem] border border-slate-200 shadow-sm hover:shadow-xl transition-all duration-300">
          <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mb-8">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          </div>
          <h3 className="text-xl font-black text-slate-800 mb-2">Import from YouTube</h3>
          <p className="text-sm text-slate-500 mb-8 font-medium leading-relaxed">Extract transcripts from YouTube videos to add your spoken wisdom to the brain.</p>

          <div className="flex gap-3">
            <input
              type="text"
              placeholder="https://youtube.com/watch?v=..."
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              className="flex-1 px-5 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl text-sm font-medium outline-none focus:ring-2 focus:ring-red-500 transition-all"
            />
            <button
              onClick={handleYoutubeIngest}
              disabled={ingestingYoutube || !youtubeUrl}
              className="px-8 py-3.5 bg-red-600 text-white rounded-2xl text-sm font-black hover:bg-red-700 disabled:opacity-50 transition-all shadow-lg shadow-red-100"
            >
              {ingestingYoutube ? '...' : 'Add'}
            </button>
          </div>
        </div>

        {/* Podcast Card */}
        <div className="bg-white p-10 rounded-[2.5rem] border border-slate-200 shadow-sm hover:shadow-xl transition-all duration-300">
          <div className="w-14 h-14 bg-purple-50 text-purple-600 rounded-2xl flex items-center justify-center mb-8">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
          </div>
          <h3 className="text-xl font-black text-slate-800 mb-2">Import Podcasts</h3>
          <p className="text-sm text-slate-500 mb-8 font-medium leading-relaxed">Sync your latest podcast episodes via RSS feed and transcribe them automatically.</p>

          <div className="flex gap-3">
            <input
              type="text"
              placeholder="https://feed.podbean.com/..."
              value={podcastUrl}
              onChange={(e) => setPodcastUrl(e.target.value)}
              className="flex-1 px-5 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl text-sm font-medium outline-none focus:ring-2 focus:ring-purple-500 transition-all"
            />
            <button
              onClick={handlePodcastIngest}
              disabled={ingestingPodcast || !podcastUrl}
              className="px-8 py-3.5 bg-purple-600 text-white rounded-2xl text-sm font-black hover:bg-purple-700 disabled:opacity-50 transition-all shadow-lg shadow-purple-100"
            >
              {ingestingPodcast ? '...' : 'Add'}
            </button>
          </div>
        </div>

        {/* X Thread Card */}
        <div className="bg-white p-10 rounded-[2.5rem] border border-slate-200 shadow-sm hover:shadow-xl transition-all duration-300">
          <div className="w-14 h-14 bg-slate-900 text-white rounded-2xl flex items-center justify-center mb-8">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 2L2 22h20L12 2zM12 18l-4-4h8l-4 4z" />
            </svg>
          </div>
          <h3 className="text-xl font-black text-slate-800 mb-2">Sync X Threads</h3>
          <p className="text-sm text-slate-500 mb-8 font-medium leading-relaxed">Turn your X (Twitter) threads and viral insights into permanent memory units.</p>

          <div className="flex gap-3">
            <input
              type="text"
              placeholder="https://x.com/user/status/..."
              value={xUrl}
              onChange={(e) => setXUrl(e.target.value)}
              className="flex-1 px-5 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl text-sm font-medium outline-none focus:ring-2 focus:ring-slate-900 transition-all"
            />
            <button
              onClick={handleXIngest}
              disabled={ingestingX || !xUrl}
              className="px-8 py-3.5 bg-slate-900 text-white rounded-2xl text-sm font-black hover:bg-black disabled:opacity-50 transition-all shadow-lg shadow-slate-200"
            >
              {ingestingX ? '...' : 'Add'}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 text-red-600 p-6 rounded-[2rem] text-sm font-bold flex items-center gap-4">
          <div className="w-8 h-8 bg-red-100 rounded-full flex items-center justify-center">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          </div>
          {error}
        </div>
      )}

      {/* Sources List */}
      <div className="bg-white rounded-[2.5rem] border border-slate-200 overflow-hidden shadow-sm">
        <div className="p-8 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-lg font-black text-slate-800">Your Sources</h3>
          <span className="text-xs font-black text-slate-400 bg-slate-50 px-4 py-1.5 rounded-full">{sources.length} Total</span>
        </div>

        {loading ? (
          <div className="p-20 flex justify-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
          </div>
        ) : sources.length === 0 ? (
          <div className="p-32 text-center">
            <div className="text-slate-200 mb-6 flex justify-center">
              <svg className="w-24 h-24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
            </div>
            <h4 className="text-xl font-black text-slate-800">Brain is empty</h4>
            <p className="text-sm text-slate-500 max-w-xs mx-auto mt-3 font-medium">Upload your first document or YouTube link above to start building your persona.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50/50">
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Source Name</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Type</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Status</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Added On</th>
                  <th className="px-8 py-5 text-right"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {sources.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/50 transition-colors group">
                    <td className="px-8 py-6">
                      <div className="font-bold text-slate-800 text-sm truncate max-w-sm mb-1">{s.filename}</div>
                      {s.groups && s.groups.length > 0 && (
                        <div className="flex gap-1 flex-wrap mt-1">
                          {s.groups.map((group: { id: string; name: string }) => (
                            <span
                              key={group.id}
                              className="px-2 py-0.5 text-xs bg-blue-100 text-blue-800 rounded"
                            >
                              {group.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-8 py-6">
                      {s.filename.startsWith('YouTube:') ? (
                        <span className="bg-red-50 text-red-600 text-[10px] font-black px-3 py-1.5 rounded-xl">YOUTUBE</span>
                      ) : s.filename.startsWith('Podcast:') ? (
                        <span className="bg-purple-50 text-purple-600 text-[10px] font-black px-3 py-1.5 rounded-xl">PODCAST</span>
                      ) : s.filename.startsWith('X Thread:') ? (
                        <span className="bg-slate-900 text-white text-[10px] font-black px-3 py-1.5 rounded-xl">X THREAD</span>
                      ) : s.filename.endsWith('.pdf') ? (
                        <span className="bg-indigo-50 text-indigo-600 text-[10px] font-black px-3 py-1.5 rounded-xl">PDF</span>
                      ) : (
                        <span className="bg-slate-50 text-slate-600 text-[10px] font-black px-3 py-1.5 rounded-xl">FILE</span>
                      )}
                    </td>
                    <td className="px-8 py-6">
                      <span className={`inline-flex items-center gap-2 text-[10px] font-black ${s.status === 'processed' ? 'text-green-600' : 'text-yellow-600 animate-pulse'
                        }`}>
                        <span className={`w-2 h-2 rounded-full ${s.status === 'processed' ? 'bg-green-500' : 'bg-yellow-500'}`}></span>
                        {s.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-8 py-6 text-xs font-bold text-slate-400">
                      {new Date(s.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </td>
                    <td className="px-8 py-6 text-right">
                      <button
                        onClick={() => handleDelete(s.id)}
                        className="text-slate-300 hover:text-red-600 transition-all p-2 hover:bg-red-50 rounded-xl"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
