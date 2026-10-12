"""Fictional Atlas Morocco catalog constants used by the local generator.

These are merchandising examples, not claims about real suppliers, prices, or
vehicle fitment. Every database record is created anew in the isolated target.
"""

SUPPLIERS = (
    ("supplier_rifroute", "RifRoute Parts House", "Oujda"),
    ("supplier_casavolt", "CasaVolt Parts Desk", "Casablanca"),
    ("supplier_meknes_motion", "Meknes Motion Supply", "Meknes"),
    ("supplier_safidrive", "SafiDrive Wholesale", "Safi"),
    ("supplier_atlas_rubber", "Atlas Rubber and Belts", "Marrakech"),
    ("supplier_urban_cooling", "Urban Cooling Parts", "Rabat"),
    ("supplier_souss_electro", "Souss Electro Comptoir", "Agadir"),
    ("supplier_northline_filters", "Northline Filter Depot", "Tangier"),
)

CUSTOMERS = (
    ("customer_marrakech_01", "Atelier Al Amal", "Marrakech"),
    ("customer_marrakech_02", "Garage Bab Doukkala", "Marrakech"),
    ("customer_casablanca_01", "Casa Ligne Auto Service", "Casablanca"),
    ("customer_casablanca_02", "Anfa Fleet Workshop", "Casablanca"),
    ("customer_agadir_01", "Garage Souss Motor", "Agadir"),
    ("customer_agadir_02", "Atelier Oued Souss", "Agadir"),
    ("customer_fes_01", "Atelier Saiss Route", "Fes"),
    ("customer_fes_02", "Garage Cedre Mecanique", "Fes"),
    ("customer_rabat_01", "Rabat Atelier Urbain", "Rabat"),
    ("customer_rabat_02", "Bouregreg Fleet Services", "Rabat"),
    ("customer_tangier_01", "Garage Detroit du Nord", "Tangier"),
    ("customer_oujda_01", "Atelier Rif Orient", "Oujda"),
    ("customer_safi_01", "Garage Safi Horizon", "Safi"),
    ("customer_meknes_01", "Depot Meknes Motor", "Meknes"),
    ("customer_kenitra_01", "Kenitra Auto Comptoir", "Kenitra"),
    ("customer_tetouan_01", "Tetouan Service Lane", "Tetouan"),
    ("customer_essaouira_01", "Essaouira Garage Workshop", "Essaouira"),
    ("customer_eljadida_01", "El Jadida Parts Counter", "El Jadida"),
)

WAREHOUSES = (
    ("warehouse_atlas_central", "Atlas Central Warehouse", "ATC", "Marrakech"),
    ("warehouse_south_depot", "South Service Depot", "ASD", "Agadir"),
)

CATEGORIES = (
    {
        "key": "filtration_engine_service",
        "code": "FLT",
        "count": 35,
        "price": (38, 460),
        "suppliers": ("supplier_rifroute", "supplier_northline_filters"),
        "families": (
            "Engine Oil Filter Element",
            "Spin-On Oil Filter",
            "Cabin Air Filter",
            "Carbon Cabin Filter",
            "Air Intake Filter",
            "Panel Air Filter",
            "Diesel Fuel Filter",
            "Fuel Filter Element",
            "Water Separator Filter",
            "Transmission Filter",
            "Hydraulic Filter Element",
            "Oil Filter Cartridge",
        ),
    },
    {
        "key": "braking",
        "code": "BRK",
        "count": 30,
        "price": (74, 1480),
        "suppliers": ("supplier_meknes_motion", "supplier_safidrive"),
        "families": (
            "Front Brake Pad Set",
            "Rear Brake Pad Set",
            "Brake Shoe Set",
            "Brake Disc Pair",
            "Brake Caliper Repair Kit",
            "Brake Hose",
            "Brake Wear Sensor",
            "Brake Master Cylinder",
            "Wheel Cylinder",
            "Brake Fluid",
        ),
    },
    {
        "key": "suspension_steering",
        "code": "SUS",
        "count": 25,
        "price": (90, 1750),
        "suppliers": ("supplier_safidrive", "supplier_meknes_motion"),
        "families": (
            "Front Stabilizer Link",
            "Tie Rod End",
            "Steering Rack Boot",
            "Control Arm Bushing",
            "Ball Joint",
            "Suspension Mount",
            "Shock Absorber Mount",
            "Wheel Bearing Kit",
            "Steering Linkage",
        ),
    },
    {
        "key": "electrical_batteries",
        "code": "ELC",
        "count": 25,
        "price": (42, 2250),
        "suppliers": ("supplier_casavolt", "supplier_souss_electro"),
        "families": (
            "Starter Battery 12 V",
            "Alternator Belt Tensioner",
            "Starter Motor Solenoid",
            "Headlamp Bulb Pair",
            "Wiper Motor",
            "Alternator Regulator",
            "Battery Terminal Set",
            "Window Switch",
            "Fuse Assortment",
        ),
    },
    {
        "key": "cooling_belts_drivetrain",
        "code": "CLD",
        "count": 20,
        "price": (55, 2480),
        "suppliers": ("supplier_atlas_rubber", "supplier_urban_cooling"),
        "families": (
            "Engine Coolant",
            "Radiator Hose",
            "Thermostat",
            "Water Pump",
            "Drive Belt",
            "Timing Belt Kit",
            "Coolant Expansion Tank",
            "Radiator Cap",
        ),
    },
    {
        "key": "ignition_sensors_fluids",
        "code": "IGN",
        "count": 15,
        "price": (35, 980),
        "suppliers": ("supplier_souss_electro", "supplier_casavolt"),
        "families": (
            "Iridium Spark Plug",
            "Ignition Coil",
            "Engine Temperature Sensor",
            "Crankshaft Position Sensor",
            "Engine Oil",
            "Power Steering Fluid",
            "Air Flow Sensor",
            "Oxygen Sensor",
        ),
    },
)

DEMAND_CLASSES = ("fast", "steady", "intermittent", "slow")
