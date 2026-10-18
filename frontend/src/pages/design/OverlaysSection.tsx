import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { ExampleLabel, Section } from "./Section";

export function OverlaysSection() {
  return (
    <Section
      id="dialog-snackbar-tabs"
      title="Dialog, snackbar and tabs"
      description="A dialog asks before something important. A snackbar at the bottom confirms that something happened. Tabs switch between views of the same thing."
    >
      <Card>
        <CardContent className="grid gap-8">
          <div className="grid gap-3">
            <ExampleLabel>Dialog (Esc closes it) · Snackbar</ExampleLabel>
            <div className="flex flex-wrap gap-3">
              <Dialog>
                <DialogTrigger asChild>
                  <Button variant="outlined">Delete part…</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Delete “Brake pads (front)”?</DialogTitle>
                    <DialogDescription>
                      Its sales history stays in reports. You can add the part again later.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <DialogClose asChild>
                      <Button variant="text">Cancel</Button>
                    </DialogClose>
                    <DialogClose asChild>
                      <Button variant="danger" onClick={() => toast.success("Part deleted")}>
                        Delete part
                      </Button>
                    </DialogClose>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
              <Button
                variant="outlined"
                onClick={() =>
                  toast.success("Stock updated", { description: "Oil filter: 1,240 in Casablanca" })
                }
              >
                Show snackbar
              </Button>
              <Button variant="outlined" onClick={() => toast.error("Couldn't save. Try again.")}>
                Show error snackbar
              </Button>
            </div>
          </div>

          <div className="grid gap-3">
            <ExampleLabel>Tabs (arrow keys move between them)</ExampleLabel>
            <Tabs defaultValue="7">
              <TabsList>
                <TabsTrigger value="7">Next 7 days</TabsTrigger>
                <TabsTrigger value="30">Next 30 days</TabsTrigger>
                <TabsTrigger value="60">Next 60 days</TabsTrigger>
              </TabsList>
              <TabsContent value="7" className="text-body-medium text-on-surface-variant">
                Content for the next 7 days.
              </TabsContent>
              <TabsContent value="30" className="text-body-medium text-on-surface-variant">
                Content for the next 30 days.
              </TabsContent>
              <TabsContent value="60" className="text-body-medium text-on-surface-variant">
                Content for the next 60 days.
              </TabsContent>
            </Tabs>
          </div>
        </CardContent>
      </Card>
    </Section>
  );
}
