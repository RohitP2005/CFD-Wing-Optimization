import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { WingParams, ConfigDefaults } from "@/lib/api";

interface Props {
  defaults: ConfigDefaults;
  initial: WingParams;
  onPreview: (p: WingParams) => void;
  onSave?: (p: WingParams) => void;
  isLoading?: boolean;
  saveLabel?: string;
}

const schema = z
  .object({
    span_m: z.coerce.number().positive(),
    root_chord_m: z.coerce.number().positive(),
    tip_chord_m: z.coerce.number().positive(),
    sweep_deg: z.coerce.number(),
    twist_deg: z.coerce.number(),
    airfoil_id: z.string().min(1),
  })
  .refine((d) => d.tip_chord_m <= d.root_chord_m, {
    message: "Tip chord must be ≤ root chord",
    path: ["tip_chord_m"],
  });

const FIELDS: Array<{ key: keyof WingParams; label: string; unit?: string; step?: number }> = [
  { key: "span_m", label: "Span", unit: "m", step: 0.1 },
  { key: "root_chord_m", label: "Root chord", unit: "m", step: 0.05 },
  { key: "tip_chord_m", label: "Tip chord", unit: "m", step: 0.05 },
  { key: "sweep_deg", label: "Sweep angle", unit: "°", step: 0.5 },
  { key: "twist_deg", label: "Twist angle", unit: "°", step: 0.5 },
];

export function WingParameterForm({ defaults, initial, onPreview, onSave, isLoading, saveLabel }: Props) {
  const form = useForm<WingParams>({
    resolver: zodResolver(schema) as any,
    defaultValues: initial,
    mode: "onChange",
  });
  const { register, handleSubmit, formState, setValue, watch, reset } = form;

  useEffect(() => {
    reset(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(initial)]);

  const airfoilId = watch("airfoil_id");

  const submitPreview = handleSubmit((d) => onPreview(d));
  const submitSave = handleSubmit((d) => onSave?.(d));

  return (
    <form className="space-y-4" onSubmit={submitPreview}>
      <div className="grid grid-cols-2 gap-3">
        {FIELDS.map((f) => {
          const b = defaults.bounds?.[f.key as string];
          const err = (formState.errors as any)[f.key]?.message as string | undefined;
          const rangeStr = b ? `${b.min} - ${b.max}` : "";
          return (
            <div key={f.key} className="space-y-1">
              <Label htmlFor={f.key} className="text-[11px] uppercase tracking-wider text-muted-foreground font-mono">
                <div className="flex justify-between">
                  <span>{f.label}</span>
                  {f.unit && <span className="text-muted-foreground/60">[{f.unit}]</span>}
                </div>
                {b && (
                  <div className="text-[10px] font-normal text-muted-foreground/70 mt-0.5">
                    Range: {rangeStr}
                  </div>
                )}
              </Label>
              <Input
                id={f.key}
                type="number"
                step={f.step ?? 0.1}
                min={b?.min}
                max={b?.max}
                className="font-mono"
                {...register(f.key as any, { valueAsNumber: true })}
              />
              {err && <p className="text-[11px] text-destructive">{err}</p>}
            </div>
          );
        })}
        <div className="space-y-1 col-span-2">
          <Label className="text-[11px] uppercase tracking-wider text-muted-foreground font-mono">
            Airfoil
          </Label>
          <Select value={airfoilId} onValueChange={(v) => setValue("airfoil_id", v, { shouldValidate: true })}>
            <SelectTrigger className="font-mono">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(defaults.airfoils ?? ["NACA0012", "NACA2412", "NACA4412"]).map((a) => (
                <SelectItem key={a} value={a} className="font-mono">
                  {a}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex gap-2 pt-2">
        <Button type="submit" disabled={isLoading || !formState.isValid} className="flex-1">
          {isLoading ? "Computing…" : "Preview"}
        </Button>
        {onSave && (
          <Button
            type="button"
            variant="outline"
            onClick={submitSave}
            disabled={!formState.isValid}
          >
            {saveLabel ?? "Save"}
          </Button>
        )}
      </div>
    </form>
  );
}