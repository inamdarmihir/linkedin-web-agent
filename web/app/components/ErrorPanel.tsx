export default function ErrorPanel({
  label,
  detail,
}: {
  label: string;
  detail: string | null;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-red-300 bg-red-50 p-5 text-red-800 shadow-sm">
      <h2 className="text-sm font-semibold">{label}</h2>
      {detail && <p className="text-sm">{detail}</p>}
    </div>
  );
}
