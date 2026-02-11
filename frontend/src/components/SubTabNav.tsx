interface SubTab {
  id: string;
  label: string;
}

interface Props {
  tabs: SubTab[];
  active: string;
  onChange: (id: string) => void;
}

export default function SubTabNav({ tabs, active, onChange }: Props) {
  return (
    <div className="flex gap-1 rounded-xl bg-surface-overlay/50 border border-border-subtle backdrop-blur-sm p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            active === tab.id
              ? "bg-primary-glow text-primary shadow-[0_0_8px_rgba(0,212,255,0.2)]"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
