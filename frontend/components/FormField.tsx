import { Children, ReactElement, ReactNode, cloneElement, isValidElement, useId } from "react";

type ControlProps = {
  id?: string;
  name?: string;
  required?: boolean;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
};

export function FormField({
  label,
  name,
  required = false,
  optional = false,
  hint,
  error,
  children,
}: {
  label: string;
  name?: string;
  required?: boolean;
  optional?: boolean;
  hint?: string;
  error?: string;
  children: ReactElement<ControlProps>;
}) {
  const generatedId = useId();
  const controlId = children.props.id || name || generatedId;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const describedBy = [children.props["aria-describedby"], hintId, errorId].filter(Boolean).join(" ") || undefined;
  const control = cloneElement(children, {
    id: controlId,
    name: children.props.name || name,
    required: children.props.required ?? required,
    "aria-invalid": Boolean(error),
    "aria-describedby": describedBy,
  });

  return (
    <label className={`form-field${error ? " form-field--error" : ""}`} htmlFor={controlId}>
      <span className="form-field__label">
        <span>{label}</span>
        {required ? <span className="form-field__required">Required</span> : null}
        {optional ? <span className="form-field__optional">Optional</span> : null}
      </span>
      {control}
      {hint ? <span className="form-field__hint" id={hintId}>{hint}</span> : null}
      {error ? <span className="form-field__error" id={errorId} role="alert">{error}</span> : null}
    </label>
  );
}

export function FormSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <fieldset className="form-section">
      <legend>{title}</legend>
      {description ? <p className="form-section__description">{description}</p> : null}
      <div className="form-grid">{Children.toArray(children)}</div>
    </fieldset>
  );
}
