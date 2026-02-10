'use client';

import { createBrowserClient } from '@supabase/auth-helpers-nextjs';

// Default values for development - Vercel deployments MUST set these in dashboard
const DEFAULT_SUPABASE_URL = 'https://jvtffdbuwyhmcynauety.supabase.co';
const DEFAULT_SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dGZmZGJ1d3lobWN5bmF1ZXR5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYwMTY1MzksImV4cCI6MjA4MTU5MjUzOX0.tRpBHBhL2GM9s6sSncrVrNnmtwxrzED01SzwjKRb37E';

function getEnvVar(name: string, defaultValue?: string): string {
    const value = process.env[name] || defaultValue;
    if (!value) {
        console.error(`Missing required environment variable: ${name}`);
        // Return placeholder to prevent crash - actual error will show on auth attempt
        return 'missing';
    }
    return value;
}

export function createClient() {
    const url = getEnvVar('NEXT_PUBLIC_SUPABASE_URL', DEFAULT_SUPABASE_URL);
    const key = getEnvVar('NEXT_PUBLIC_SUPABASE_ANON_KEY', DEFAULT_SUPABASE_ANON_KEY);
    
    if (url === 'missing' || key === 'missing') {
        console.error('Supabase credentials not configured. Please set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in your Vercel dashboard.');
    }
    
    return createBrowserClient(url, key);
}

// Singleton instance for use in components
let browserClient: ReturnType<typeof createBrowserClient> | null = null;

export function getSupabaseClient() {
    if (!browserClient) {
        browserClient = createClient();
    }
    return browserClient;
}
