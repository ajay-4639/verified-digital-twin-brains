import { createServerClient, type CookieOptions } from '@supabase/auth-helpers-nextjs';
import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
    const requestUrl = new URL(request.url);
    const code = requestUrl.searchParams.get('code');
    const error = requestUrl.searchParams.get('error');
    const errorDescription = requestUrl.searchParams.get('error_description');
    const redirect = requestUrl.searchParams.get('redirect') || '/dashboard';

    // Handle OAuth errors
    if (error) {
        console.error('OAuth error:', error, errorDescription);
        const loginUrl = new URL('/auth/login', requestUrl.origin);
        loginUrl.searchParams.set('error', error);
        if (errorDescription) {
            loginUrl.searchParams.set('error_description', errorDescription);
        }
        if (redirect && redirect !== '/dashboard') {
            loginUrl.searchParams.set('redirect', redirect);
        }
        return NextResponse.redirect(loginUrl);
    }

    if (!code) {
        // No code parameter - redirect to login
        const loginUrl = new URL('/auth/login', requestUrl.origin);
        if (redirect && redirect !== '/dashboard') {
            loginUrl.searchParams.set('redirect', redirect);
        }
        return NextResponse.redirect(loginUrl);
    }

    try {
        const cookieStore = await cookies();

        const supabase = createServerClient(
            process.env.NEXT_PUBLIC_SUPABASE_URL!,
            process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
            {
                cookies: {
                    get(name: string) {
                        return cookieStore.get(name)?.value;
                    },
                    set(name: string, value: string, options: CookieOptions) {
                        cookieStore.set({ name, value, ...options });
                    },
                    remove(name: string, options: CookieOptions) {
                        cookieStore.set({ name, value: '', ...options });
                    },
                },
            }
        );

        const { data: sessionData, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
        
        if (exchangeError) {
            console.error('Session exchange error:', exchangeError);
            const loginUrl = new URL('/auth/login', requestUrl.origin);
            loginUrl.searchParams.set('error', 'session_exchange_failed');
            if (redirect && redirect !== '/dashboard') {
                loginUrl.searchParams.set('redirect', redirect);
            }
            return NextResponse.redirect(loginUrl);
        }

        // Redirect to the dashboard or specified redirect path
        return NextResponse.redirect(new URL(redirect, requestUrl.origin));
    } catch (error) {
        console.error('Callback error:', error);
        const loginUrl = new URL('/auth/login', requestUrl.origin);
        loginUrl.searchParams.set('error', 'callback_error');
        if (redirect && redirect !== '/dashboard') {
            loginUrl.searchParams.set('redirect', redirect);
        }
        return NextResponse.redirect(loginUrl);
    }
}
