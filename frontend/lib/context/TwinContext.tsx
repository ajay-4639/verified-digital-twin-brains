'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import type { AuthChangeEvent, Session } from '@supabase/supabase-js';

// ============================================================================
// Types
// ============================================================================

export interface Twin {
    id: string;
    name: string;
    owner_id: string;
    tenant_id: string;
    specialization: string;
    is_active: boolean;
    settings?: Record<string, unknown>;
    system_instructions?: string;
    created_at: string;
    updated_at: string;
}

export interface UserProfile {
    id: string;
    email: string;
    full_name?: string;
    avatar_url?: string;
    tenant_id?: string;
    onboarding_completed: boolean;
    created_at?: string;
}

interface TwinContextType {
    // User state
    user: UserProfile | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    error: string | null;  // NEW: Explicit error state

    // Twin state
    twins: Twin[];
    activeTwin: Twin | null;

    // Actions
    setActiveTwin: (twinId: string) => void;
    refreshTwins: () => Promise<void>;
    syncUser: () => Promise<UserProfile | null>;
}

const TwinContext = createContext<TwinContextType | undefined>(undefined);

// ============================================================================
// Provider Component
// ============================================================================

export function TwinProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<UserProfile | null>(null);
    const [twins, setTwins] = useState<Twin[]>([]);
    const [activeTwin, setActiveTwinState] = useState<Twin | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);  // NEW: Track errors

    const supabase = getSupabaseClient();
    const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

    // Get auth token (with timeout and retry logic)
    const getToken = useCallback(async (): Promise<string | null> => {
        const maxRetries = 3;
        const baseTimeout = 5000; // 5 seconds per attempt

        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                console.log(`[TwinContext] getToken attempt ${attempt}/${maxRetries}`);
                const timeoutPromise = new Promise<null>((resolve) => {
                    setTimeout(() => resolve(null), baseTimeout * attempt);
                });

                const result = await Promise.race([
                    supabase.auth.getSession(),
                    timeoutPromise
                ]) as any;

                const token = result?.data?.session?.access_token || null;
                if (token) {
                    console.log('[TwinContext] Token obtained successfully');
                    return token;
                }

                // No token on this attempt, continue to retry
                console.warn(`[TwinContext] No token on attempt ${attempt}`);
            } catch (e) {
                console.warn(`[TwinContext] getToken attempt ${attempt} failed:`, e);
            }
        }

        console.error('[TwinContext] All token retrieval attempts failed');
        return null;
    }, [supabase]);

    // Sync user with backend (creates user record if first login)
    const syncUser = useCallback(async (): Promise<UserProfile | null> => {
        try {
            const token = await getToken();
            if (!token) return null;

            const response = await fetch(`${API_URL}/auth/sync-user`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                console.error('Failed to sync user:', response.statusText);
                return null;
            }

            const data = await response.json();
            setUser(data.user);
            return data.user;
        } catch (error) {
            console.error('Error syncing user:', error);
            return null;
        }
    }, [API_URL, getToken]);

    // Fetch user's twins
    const refreshTwins = useCallback(async () => {
        console.log('[TwinContext] refreshTwins called');
        setError(null); // Clear previous error

        try {
            const token = await getToken();

            if (!token) {
                console.error('[TwinContext] No auth token available - user may need to sign in');
                setError('Authentication required. Please sign in.');
                return;
            }

            // Try authenticated endpoint
            console.log('[TwinContext] Trying authenticated /auth/my-twins');
            const response = await fetch(`${API_URL}/auth/my-twins`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error(`[TwinContext] API error ${response.status}: ${errorText}`);
                setError(`Failed to fetch twins: ${response.status}`);
                return;
            }

            const data = await response.json();

            // Defensive: handle both raw array and object envelope formats
            const twinsList = Array.isArray(data) ? data : (data.twins || []);
            console.log('[TwinContext] Got twins:', twinsList.length);
            setTwins(twinsList);

            // Set active twin from localStorage or first twin
            const savedTwinId = localStorage.getItem('activeTwinId');
            const activeTwinFromList = twinsList.find((t: Twin) => t.id === savedTwinId) || twinsList[0];

            if (activeTwinFromList) {
                setActiveTwinState(activeTwinFromList);
                localStorage.setItem('activeTwinId', activeTwinFromList.id);
                console.log('[TwinContext] Active twin set:', activeTwinFromList.id);
            } else {
                console.log('[TwinContext] No twins available to set as active');
            }
        } catch (err) {
            console.error('[TwinContext] Error fetching twins:', err);
            setError('Network error fetching twins');
        }
    }, [API_URL, getToken]);

    // Set active twin
    const setActiveTwin = useCallback((twinId: string) => {
        const twin = twins.find(t => t.id === twinId);
        if (twin) {
            setActiveTwinState(twin);
            localStorage.setItem('activeTwinId', twinId);
        }
    }, [twins]);

    // Initialize on auth state change
    useEffect(() => {
        let mounted = true;

        const initialize = async () => {
            console.log('[TwinContext] Starting initialization...');
            setIsLoading(true);

            try {
                // Try to get session with a timeout to prevent hanging
                console.log('[TwinContext] Getting session with timeout...');

                // Create a promise that rejects after 15 seconds
                const timeoutPromise = new Promise((_, reject) => {
                    setTimeout(() => reject(new Error('Session timeout')), 15000);
                });

                // Race the session fetch against the timeout
                let session = null;
                try {
                    const result = await Promise.race([
                        supabase.auth.getSession(),
                        timeoutPromise
                    ]) as any;
                    session = result?.data?.session;
                    console.log('[TwinContext] Session result:', session ? 'exists' : 'null');
                } catch (e) {
                    console.warn('[TwinContext] Session fetch timed out or failed, continuing without auth');
                }

                if (mounted) {
                    if (session) {
                        console.log('[TwinContext] Calling syncUser...');
                        await syncUser();
                        console.log('[TwinContext] syncUser done, calling refreshTwins...');
                    }
                    // Always try to fetch twins (even without session, some endpoints may be public)
                    await refreshTwins();
                    console.log('[TwinContext] refreshTwins complete');
                }
            } catch (error) {
                console.error('[TwinContext] Initialization error:', error);
            } finally {
                console.log('[TwinContext] Finally block, setting isLoading to false');
                if (mounted) {
                    setIsLoading(false);
                }
            }
        };

        initialize();

        // Listen for auth changes
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (event: AuthChangeEvent, session: Session | null) => {
                if (event === 'SIGNED_IN' && session && mounted) {
                    setIsLoading(true);
                    await syncUser();
                    await refreshTwins();
                    setIsLoading(false);
                } else if (event === 'SIGNED_OUT' && mounted) {
                    setUser(null);
                    setTwins([]);
                    setActiveTwinState(null);
                    localStorage.removeItem('activeTwinId');
                }
            }
        );

        return () => {
            mounted = false;
            subscription.unsubscribe();
        };
    }, [supabase, syncUser, refreshTwins]);

    const value: TwinContextType = {
        user,
        isAuthenticated: !!user,
        isLoading,
        error,  // NEW: Include error state
        twins,
        activeTwin,
        setActiveTwin,
        refreshTwins,
        syncUser
    };

    return (
        <TwinContext.Provider value={value}>
            {children}
        </TwinContext.Provider>
    );
}

// ============================================================================
// Hook
// ============================================================================

export function useTwin(): TwinContextType {
    const context = useContext(TwinContext);
    if (context === undefined) {
        throw new Error('useTwin must be used within a TwinProvider');
    }
    return context;
}

// Convenience hooks
export function useActiveTwin(): Twin | null {
    const { activeTwin } = useTwin();
    return activeTwin;
}

export function useUser(): UserProfile | null {
    const { user } = useTwin();
    return user;
}
