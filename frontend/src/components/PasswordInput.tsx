import { EyeIcon, EyeOffIcon } from "lucide-react";
import { useState } from "react";
import type * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n";

// A password field with an eye button at the end side to show or hide what was typed.
// Use it for every password. Works inside FormField: <PasswordInput {...field} />.
export function PasswordInput(props: Omit<React.ComponentProps<"input">, "type">) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <Input {...props} type={visible ? "text" : "password"} className="pe-11" />
      <Button
        type="button"
        variant="subtle"
        size="icon-sm"
        className="absolute end-1 top-1/2 -translate-y-1/2 text-muted-foreground"
        aria-label={visible ? t.common.hidePassword : t.common.showPassword}
        aria-controls={props.id}
        // Keeps the cursor in the field when the button is clicked with the mouse.
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => setVisible(!visible)}
      >
        {visible ? <EyeOffIcon aria-hidden="true" /> : <EyeIcon aria-hidden="true" />}
      </Button>
    </div>
  );
}
