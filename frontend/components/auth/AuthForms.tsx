"use client";

import Link from "next/link";
import { useState } from "react";
import Button from "@/components/ui/Button";
import { acceptInvitation, login, setSessionToken, signup } from "@/lib/api";
import type { InvitationRead, SessionRead } from "@/lib/types";

// V3 sign-in screens (brain/permissions.md). Full-screen like Onboarding: no
// product chrome before someone is signed in. A successful call stores the
// access token in the session cookie (lib/api.ts) and leaves the page with a
// full navigation, so every Server Component renders with the new session.

function AuthShell({ eyebrow, title, subtitle, children }: { eyebrow: string; title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-col items-center bg-bg px-6 py-10">
      <div className="flex w-full max-w-3xl items-center gap-2.5">
        <div className="flex h-[26px] w-[26px] items-center justify-center rounded-lg bg-accent font-display text-[13px] font-semibold text-white">B</div>
        <span className="font-display text-[15px] font-semibold">AI Business OS</span>
      </div>
      <div className="animate-reveal mt-12 w-full max-w-[480px] rounded-[20px] border border-border bg-surface p-8 shadow-card md:p-10">
        <p className="text-[12.5px] font-semibold uppercase tracking-wide text-accent-strong">{eyebrow}</p>
        <h1 className="mt-3 font-display text-[30px] italic leading-tight">{title}</h1>
        {subtitle && <p className="mt-3 text-[14.5px] text-text-soft">{subtitle}</p>}
        <div className="mt-8">{children}</div>
      </div>
    </div>
  );
}

function Field({
  label,
  type = "text",
  value,
  onChange,
  autoComplete,
  hint,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  hint?: string;
}) {
  return (
    <label className="mb-5 block">
      <span className="mb-2 block text-[13px] font-semibold text-text">{label}</span>
      <input
        type={type}
        value={value}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border-[1.5px] border-border-strong px-4 py-3 text-[14.5px] outline-none focus:border-accent"
      />
      {hint && <span className="mt-1.5 block text-[12px] text-text-faint">{hint}</span>}
    </label>
  );
}

function useSubmit(action: () => Promise<SessionRead>, destination: () => string) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = await action();
      setSessionToken(session.access_token);
      window.location.assign(destination());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue.");
      setBusy(false);
    }
  }

  return { busy, error, submit };
}

function safeNext(): string {
  const next = new URLSearchParams(window.location.search).get("next");
  // Only a path inside the app, never another site.
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { busy, error, submit } = useSubmit(() => login({ email, password }), safeNext);

  return (
    <AuthShell eyebrow="Connexion" title="Bon retour" subtitle="Connectez-vous à l'espace de votre entreprise.">
      <form onSubmit={submit}>
        <Field label="Adresse e-mail" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <Field label="Mot de passe" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
        {error && <p className="mb-4 text-[13px] text-danger">{error}</p>}
        <Button type="submit" loading={busy} disabled={!email || !password} className="w-full">
          Se connecter
        </Button>
      </form>
      <p className="mt-6 text-center text-[13px] text-text-soft">
        Nouvelle entreprise ?{" "}
        <Link href="/signup" className="font-semibold text-accent-strong hover:underline">
          Créer un compte
        </Link>
      </p>
    </AuthShell>
  );
}

export function SignupForm() {
  const [companyName, setCompanyName] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { busy, error, submit } = useSubmit(
    () => signup({ company_name: companyName.trim(), name: name.trim(), email, password }),
    () => "/onboarding",
  );

  return (
    <AuthShell
      eyebrow="Nouvelle entreprise"
      title="Créez votre espace"
      subtitle="Vous serez la direction de cet espace : vous inviterez ensuite votre équipe et choisirez ce que chacun voit."
    >
      <form onSubmit={submit}>
        <Field label="Nom de l'entreprise" value={companyName} onChange={setCompanyName} autoComplete="organization" />
        <Field label="Votre nom" value={name} onChange={setName} autoComplete="name" />
        <Field label="Adresse e-mail professionnelle" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <Field label="Mot de passe" type="password" value={password} onChange={setPassword} autoComplete="new-password" hint="10 caractères minimum." />
        {error && <p className="mb-4 text-[13px] text-danger">{error}</p>}
        <Button type="submit" loading={busy} disabled={!companyName.trim() || !name.trim() || !email || password.length < 10} className="w-full">
          Créer l&rsquo;espace
        </Button>
      </form>
      <p className="mt-6 text-center text-[13px] text-text-soft">
        Déjà un compte ?{" "}
        <Link href="/login" className="font-semibold text-accent-strong hover:underline">
          Se connecter
        </Link>
      </p>
    </AuthShell>
  );
}

export function AcceptInvitationForm({ token, invitation }: { token: string; invitation: InvitationRead | null }) {
  const [name, setName] = useState(invitation?.name ?? "");
  const [password, setPassword] = useState("");
  const { busy, error, submit } = useSubmit(() => acceptInvitation(token, { password, name: name.trim() || undefined }), () => "/");

  if (!invitation) {
    return (
      <AuthShell eyebrow="Invitation" title="Ce lien n'est plus valable" subtitle="L'invitation a expiré ou a déjà été utilisée. Demandez à votre direction de vous en envoyer une nouvelle.">
        <Link href="/login" className="text-[13.5px] font-semibold text-accent-strong hover:underline">
          Aller à la connexion
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      eyebrow={invitation.company_name}
      title="Rejoignez votre équipe"
      subtitle={`${invitation.company_name} vous invite sur AI Business OS${invitation.job_title ? ` en tant que ${invitation.job_title}` : ""}. Choisissez votre mot de passe pour activer votre compte (${invitation.email}).`}
    >
      <form onSubmit={submit}>
        <Field label="Votre nom" value={name} onChange={setName} autoComplete="name" />
        <Field label="Mot de passe" type="password" value={password} onChange={setPassword} autoComplete="new-password" hint="10 caractères minimum." />
        {error && <p className="mb-4 text-[13px] text-danger">{error}</p>}
        <Button type="submit" loading={busy} disabled={password.length < 10} className="w-full">
          Activer mon compte
        </Button>
      </form>
    </AuthShell>
  );
}
