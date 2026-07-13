using RimWorld;
using System.Linq;
using Verse;

namespace VoidShelf
{
    //public static class VoidShelfTest
    //{
    //    static VoidShelfTest()
    //    {
    //        Log.Message("[VoidShelf] Mod loaded successfully.");
    //    }
    //}

    public class VoidShelfMod : Mod
    {
        public VoidShelfMod(ModContentPack content) : base(content)
        {
            Log.Message("[VoidShelf] VoidShelfMod loaded.");
        }
    }

    public class CompProperties_DestroyerShelf : CompProperties
    {
        public CompProperties_DestroyerShelf()
        {
            this.compClass = typeof(CompDestroyerShelf);
        }
    }

    public class CompDestroyerShelf : ThingComp
    {
        public override void CompTickRare()
        {
            base.CompTickRare();

            var slotGroup = parent.GetSlotGroup();
            if (slotGroup == null) return;

            foreach (Thing thing in slotGroup.HeldThings.ToList()) // ToList to safely modify during iteration
            {
                if (thing != parent)
                {
                    Log.Message($"[VoidShelf] Destroying: {thing.Label} at {thing.Position}");
                    thing.Destroy();
                }
            }
        }
    }
}
