import { Crown, Eye, EyeOff, Pencil } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { BadgeCard } from '../components/BadgeCard';
import { CertificateCard } from '../components/CertificateCard';
import { AppShell } from '../components/layout/AppShell';
import { HamstarAvatar, HamstarMascot, VARIANT_INFO, type MascotVariant } from '../components/mascot/HamstarMascot';
import { useStore, type BadgeId } from '../store/useStore';

const BADGE_IDS: BadgeId[] = ['streak', 'noskip', 'mistakes'];

function Editable({ value, onChange, label, tint }: { value: string; onChange: (v: string) => void; label: string; tint: string }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <label className="block">
      <span className="text-xs font-bold text-ink-soft">{label}</span>
      <span className="tint-pill mt-0.5 flex items-center gap-2 rounded-full px-4 py-1.5" style={{ background: tint }}>
        <input ref={ref} className="min-w-0 flex-1 bg-transparent font-bold outline-none" value={value} placeholder="…" onChange={(e) => onChange(e.target.value)} maxLength={40} />
        <Pencil size={15} className="text-ink-soft" aria-hidden />
      </span>
    </label>
  );
}

export default function Profile() {
  const profile = useStore((s) => s.profile);
  const tiara = useStore((s) => s.stats.tiara);
  const update = useStore((s) => s.updateProfile);
  const preview = useStore((s) => s.badgePreview);
  const setPreview = useStore((s) => s.setBadgePreview);
  // the preview is for showing the app off: it never outlives the visit to this page
  useEffect(() => () => setPreview(false), [setPreview]);
  // The hamster shows off for a moment whenever a new look is picked.
  const [fresh, setFresh] = useState(false);
  useEffect(() => {
    if (!fresh) return;
    const t = setTimeout(() => setFresh(false), 1800);
    return () => clearTimeout(t);
  }, [fresh, profile.avatar]);

  return (
    <AppShell title="My Profile" sub="Your hamster, your Tiara, your badges.">
      <div className="grid gap-3 lg:grid-cols-12 [&>*]:min-w-0">
        {/* hamster profile */}
        <section className="tile flex flex-col items-center gap-3 lg:col-span-4">
          <div className="flex h-48 w-48 items-end justify-center rounded-full pb-1 shadow-[0_0_0_4px_#fffdf6,0_0_0_7px_#f0c95a] transition-colors duration-500" style={{ background: VARIANT_INFO[profile.avatar].bg }}>
            <HamstarMascot state={fresh ? 'customizing' : 'profile'} size={176} />
          </div>
          <div className="text-center">
            <div className="text-lg font-extrabold">{VARIANT_INFO[profile.avatar].name} hamster</div>
            <div className="text-sm text-ink-soft">{VARIANT_INFO[profile.avatar].blurb}</div>
          </div>
          <div className="w-full space-y-2">
            <Editable label="Name" tint="#f9dede" value={profile.name} onChange={(name) => update({ name })} />
            <Editable label="Role" tint="#dcecc9" value={profile.role} onChange={(role) => update({ role })} />
          </div>
        </section>

        <div className="space-y-3 lg:col-span-8">
          {/* choose a look */}
          <section className="tile" style={{ backgroundColor: '#e6f1d8', borderColor: '#bcd6a3' }}>
            <h2 className="mb-3 text-base">Choose your STAR</h2>
            <div className="grid grid-cols-4 gap-3 sm:grid-cols-8">
              {(Object.keys(VARIANT_INFO) as MascotVariant[]).map((id) => (
                <button
                  key={id}
                  onClick={() => {
                    update({ avatar: id });
                    setFresh(true);
                  }}
                  aria-pressed={profile.avatar === id}
                  title={`${VARIANT_INFO[id].name}: ${VARIANT_INFO[id].blurb}`}
                  className={`flex cursor-pointer flex-col items-center gap-1 rounded-2xl p-1.5 text-xs font-bold transition hover:-translate-y-0.5 ${profile.avatar === id ? 'bg-white shadow' : ''}`}
                >
                  <HamstarAvatar variant={id} size={58} ring={profile.avatar === id} />
                  {VARIANT_INFO[id].name}
                </button>
              ))}
            </div>
          </section>

          {/* tiara and certificate */}
          <div className="grid gap-3 xl:grid-cols-[13rem_1fr]">
            <section className="tile flex flex-col justify-center" style={{ backgroundColor: '#fdf1c9', borderColor: '#ecd596' }}>
              <div className="eyebrow">Tiara</div>
              <div className="flex items-center gap-2 text-4xl font-extrabold tabular-nums">
                <Crown size={30} className="text-gold-deep" /> {tiara}
              </div>
              <p className="mt-1 text-xs text-ink-soft">1 correct question = 1 Tiara</p>
            </section>
            <CertificateCard />
          </div>

          {/* badges */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base">Badges</h2>
            <button className={`btn !px-3 !py-1.5 text-sm ${preview ? 'btn-primary' : 'btn-lilac'}`} onClick={() => setPreview(!preview)} aria-pressed={preview}>
              {preview ? <EyeOff size={16} /> : <Eye size={16} />} {preview ? 'Exit Demo' : 'Preview Badges'}
            </button>
          </div>
          {preview && (
            <p className="rounded-2xl border-[1.5px] border-dashed border-lavender-deep bg-lavender-soft px-4 py-2 text-sm" role="status">
              <b>Demo preview.</b> Every badge is shown as it looks once unlocked. Nothing has been awarded: press <b>Exit Demo</b> to see the badges you have really earned.
            </p>
          )}
          <div className="grid gap-3 xl:grid-cols-3">
            {BADGE_IDS.map((b) => (
              <BadgeCard key={b} id={b} compact />
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
