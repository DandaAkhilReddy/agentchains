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
    <div className="flex gap-1 rounded-lg bg-surface-raised p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            active === tab.id
              ? "bg-emerald-500/20 text-emerald-400"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
