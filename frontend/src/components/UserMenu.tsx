import { Eye, KeyRound, LogOut, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { ROLE_BLURB, ROLE_LABEL, useAuth } from "../lib/auth";
import type { Role } from "../lib/types";

export default function UserMenu({ compact = false }: { compact?: boolean }) {
  const { me, signOut, viewAs, setViewAs } = useAuth();
  const [open, setOpen] = useState(false);
  if (!me) return null;
  const initials = me.name.split(" ").map((x) => x[0]).slice(0, 2).join("");
  return (
    <div className="user-menu">
      <button className="avatar-btn" onClick={() => setOpen(!open)} aria-expanded={open} aria-label={`Account: ${me.name}`}>
        <span className="avatar">{initials}</span>
        {!compact && <span className="who"><b>{me.name}</b><small>{viewAs ? `Viewing as ${ROLE_LABEL[viewAs]}` : ROLE_LABEL[me.primary_role]}</small></span>}
      </button>
      {open && (
        <div className="menu" role="menu" onMouseLeave={() => setOpen(false)}>
          <div className="menu-head"><span className="avatar lg">{initials}</span><div><b>{me.name}</b><small>{me.email}</small></div></div>
          <div className="menu-row"><ShieldCheck size={14} />{me.auth === "entra" ? "Signed in with Microsoft Entra ID" : "Signed in with Microsoft (demo)"}</div>
          <div className="menu-row"><KeyRound size={14} />Secrets protected by Azure Key Vault</div>
          {me.can_preview && (
            <div className="viewas">
              <span className="viewas-title"><Eye size={14} />View as</span>
              <button className={!viewAs ? "on" : ""} onClick={() => setViewAs(null)}><b>Director</b><small>{ROLE_BLURB["Luna.Director"]}</small></button>
              {me.previewable_roles.map((r: Role) => (
                <button key={r} className={viewAs === r ? "on" : ""} onClick={() => setViewAs(r)}><b>{ROLE_LABEL[r]}</b><small>{ROLE_BLURB[r]}</small></button>
              ))}
              <p className="muted small">Every switch is written to the audit log.</p>
            </div>
          )}
          <button className="menu-item" role="menuitem" onClick={signOut}><LogOut size={14} />Sign out</button>
        </div>
      )}
    </div>
  );
}
