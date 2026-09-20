import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Public routes — accessible WITHOUT a valid session.
 * Everything else requires `access_token` cookie.
 */
const PUBLIC_PATHS = ['/login', '/register', '/verify-otp'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // ── Always allow static / internal paths ─────────────────────────────────
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/favicon') ||
    pathname.startsWith('/icons') ||
    pathname.startsWith('/images') ||
    pathname.startsWith('/api')           // backend proxy / Next API routes
  ) {
    return NextResponse.next();
  }

  // ── Allow public pages ───────────────────────────────────────────────────
  const isPublic = PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + '/') || pathname.startsWith(p + '?')
  );
  if (isPublic) return NextResponse.next();

  // ── Require access_token cookie for all protected pages ──────────────────
  const token = request.cookies.get('access_token')?.value;

  if (!token) {
    const loginUrl = new URL('/login', request.url);
    if (pathname !== '/') loginUrl.searchParams.set('redirect', pathname);
    return NextResponse.redirect(loginUrl);
  }

  // ── Protect /admin — require admin role cookie ───────────────────────────
  if (pathname.startsWith('/admin')) {
    const role = request.cookies.get('user_role')?.value;
    if (role !== 'admin') {
      return NextResponse.redirect(new URL('/login?unauthorized=1', request.url));
    }
  }

  // ── Forward user identity to RSC headers ─────────────────────────────────
  const res = NextResponse.next();
  res.headers.set('x-user', request.cookies.get('username')?.value ?? '');
  res.headers.set('x-role', request.cookies.get('user_role')?.value ?? '');
  return res;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon\\.ico|icons/|images/).*)', '/'],
};
