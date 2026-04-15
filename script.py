#!/usr/bin/env python3
"""
Interactive OSM to 3D Density Map Generator
Converts OpenStreetMap features to 3D heightmaps and exports as OBJ
"""

import os
import sys
import json
import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def query_osmnx(place, feature_type="building"):
    """Query OSMnx for features"""
    import osmnx as ox
    import geopandas as gpd
    
    print(f"📥 Downloading {feature_type} data for: {place}")
    
    # Download features
    if feature_type == "building":
        gdf = ox.features_from_place(place, tags={"building": True})
    elif feature_type == "amenity":
        gdf = ox.features_from_place(place, tags={"amenity": True})
    elif feature_type == "shop":
        gdf = ox.features_from_place(place, tags={"shop": True})
    else:
        gdf = ox.features_from_place(place, tags={feature_type: True})
    
    # Keep geometry
    gdf = gdf[["geometry"]]
    print(f"   Found {len(gdf)} features")
    
    return gdf

def query_overpass(query_file_or_string, timeout=90):
    """Query Overpass API directly"""
    import requests
    
    # Load query from file or use string
    if os.path.exists(query_file_or_string):
        with open(query_file_or_string, 'r') as f:
            query = f.read()
        print(f"📁 Loading query from: {query_file_or_string}")
    else:
        query = query_file_or_string
        print(f"📝 Using direct query")
    
    print(f"🌐 Fetching data from Overpass API...")
    
    # Overpass servers
    servers = [
        "https://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter"
    ]
    
    for server in servers:
        try:
            response = requests.get(server, params={"data": query}, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            
            # Extract coordinates
            coords = []
            for element in data.get("elements", []):
                if element["type"] == "node":
                    coords.append((element["lon"], element["lat"]))
                elif "center" in element:
                    coords.append((element["center"]["lon"], element["center"]["lat"]))
            
            print(f"   Found {len(coords)} points")
            return coords
            
        except Exception as e:
            print(f"   Failed on {server}: {e}")
            continue
    
    raise Exception("All Overpass servers failed")

def create_density_heatmap(coords, grid_size=200, height_scale=10):
    """Create density heatmap from coordinates"""
    print(f"📊 Creating {grid_size}x{grid_size} density heatmap...")
    
    # Extract x and y coordinates
    x = [c[0] for c in coords]
    y = [c[1] for c in coords]
    
    # Create histogram
    heatmap, xedges, yedges = np.histogram2d(
        x, y,
        bins=grid_size,
        range=[[min(x), max(x)], [min(y), max(y)]]
    )
    
    # Normalize
    if heatmap.max() > 0:
        heatmap = heatmap / heatmap.max()
    
    return heatmap

def create_density_from_gdf(gdf, grid_size=200, height_scale=10):
    """Create density heatmap from GeoDataFrame"""
    print(f"📊 Creating {grid_size}x{grid_size} density heatmap...")
    
    # Convert to metric projection for better density calculation
    gdf_metric = gdf.to_crs(3857)
    
    # Get centroids
    points = gdf_metric.geometry.centroid
    x = points.x.values
    y = points.y.values
    
    # Create histogram
    heatmap, xedges, yedges = np.histogram2d(
        x, y,
        bins=grid_size,
        range=[[x.min(), x.max()], [y.min(), y.max()]]
    )
    
    # Normalize
    if heatmap.max() > 0:
        heatmap = heatmap / heatmap.max()
    
    return heatmap

def export_heightmap_png(heatmap, output_path, colormap="inferno"):
    """Export heatmap as PNG"""
    plt.imsave(output_path, heatmap, cmap=colormap)
    print(f"   Saved PNG: {output_path}")

def export_obj_from_heightmap(heatmap, output_path, height_scale=10, smooth=True):
    """Export heightmap as OBJ file"""
    print(f"📦 Generating OBJ mesh...")
    
    rows, cols = heatmap.shape
    verts = []
    faces = []
    
    # Create vertices
    for y in range(rows):
        for x in range(cols):
            z = heatmap[y][x] * height_scale
            verts.append((x / cols, y / rows, z))
    
    # Create faces
    for y in range(rows - 1):
        for x in range(cols - 1):
            v1 = y * cols + x
            v2 = v1 + 1
            v3 = v1 + cols + 1
            v4 = v1 + cols
            
            faces.append((v1, v2, v3, v4))
    
    # Write OBJ file
    with open(output_path, 'w') as f:
        f.write(f"# OSM Density Map\n")
        f.write(f"# Grid size: {rows}x{cols}\n")
        f.write(f"# Height scale: {height_scale}\n\n")
        
        # Write vertices
        for v in verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        
        f.write(f"\n")
        
        # Write faces
        for face in faces:
            # OBJ faces are 1-indexed
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1} {face[3]+1}\n")
    
    print(f"   Saved OBJ: {output_path}")
    return output_path

def export_mtl_with_texture(output_path, texture_path=None):
    """Export MTL file for OBJ texture mapping"""
    mtl_path = output_path.replace('.obj', '.mtl')
    
    with open(mtl_path, 'w') as f:
        f.write("# MTL file for OSM density map\n\n")
        f.write("newmtl heightmap_material\n")
        f.write("Ka 1.000 1.000 1.000\n")
        f.write("Kd 1.000 1.000 1.000\n")
        f.write("Ks 0.000 0.000 0.000\n")
        f.write("d 1.0\n")
        f.write("illum 1\n")
        
        if texture_path and os.path.exists(texture_path):
            f.write(f"map_Kd {os.path.basename(texture_path)}\n")
    
    return mtl_path

def main():
    parser = argparse.ArgumentParser(
        description="Generate 3D density maps from OpenStreetMap data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download buildings from a place
  python script.py --place "Stockholm, Sweden" --output stockholm_buildings
  
  # Use custom Overpass query file
  python script.py --query-file queries/charging_stations.txt --output charging_stations
  
  # Use direct Overpass query
  python script.py --query "[out:json]; area['ISO3166-1'='SE']; node['amenity'='charging_station'](area); out center;" --output sweden_charging
  
  # Custom grid size and height
  python script.py --place "Berlin, Germany" --grid-size 300 --height-scale 15 --output berlin_detailed
  
  # Process multiple queries from a list
  python script.py --batch queries.txt --output-dir my_exports
        """
    )
    
    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--place", help="Place name for OSMnx (e.g., 'Stockholm, Sweden')")
    input_group.add_argument("--query", help="Direct Overpass query string")
    input_group.add_argument("--query-file", help="File containing Overpass query")
    input_group.add_argument("--batch", help="File with list of queries or places (one per line)")
    
    # Output options
    parser.add_argument("--output", default="osm_density_map", help="Output filename (without extension)")
    parser.add_argument("--output-dir", default="output", help="Output directory (default: output)")
    
    # Visualization parameters
    parser.add_argument("--grid-size", type=int, default=200, help="Heatmap grid size (default: 200)")
    parser.add_argument("--height-scale", type=float, default=10, help="Height scaling factor (default: 10)")
    parser.add_argument("--colormap", default="inferno", help="Colormap for PNG (default: inferno)")
    parser.add_argument("--feature-type", default="building", help="Feature type for OSMnx (building, amenity, shop)")
    
    # Other options
    parser.add_argument("--save-heatmap", action="store_true", help="Save heatmap as NPY file")
    parser.add_argument("--no-png", action="store_true", help="Skip PNG export")
    parser.add_argument("--timeout", type=int, default=90, help="Overpass API timeout (default: 90)")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Interactive mode
    if args.interactive:
        print("\n" + "=" * 60)
        print("🎨 Interactive OSM to 3D Density Map Generator")
        print("=" * 60)
        
        while True:
            print("\nOptions:")
            print("  1. Download by place name (e.g., 'Stockholm, Sweden')")
            print("  2. Enter Overpass query")
            print("  3. Load query from file")
            print("  4. Exit")
            
            choice = input("\nChoose option (1-4): ").strip()
            
            if choice == "4":
                print("Goodbye!")
                break
            elif choice == "1":
                place = input("Enter place name: ").strip()
                if place:
                    process_place(place, args)
            elif choice == "2":
                print("Enter Overpass query (end with Ctrl+D on new line or 'END'):")
                lines = []
                while True:
                    line = input()
                    if line == "END":
                        break
                    lines.append(line)
                query = "\n".join(lines)
                if query:
                    process_query(query, args)
            elif choice == "3":
                filepath = input("Enter query file path: ").strip()
                if os.path.exists(filepath):
                    process_query_file(filepath, args)
                else:
                    print(f"File not found: {filepath}")
        return
    
    # Batch mode
    if args.batch:
        with open(args.batch, 'r') as f:
            items = [line.strip() for line in f if line.strip()]
        
        print(f"📋 Processing {len(items)} items...")
        for i, item in enumerate(items, 1):
            print(f"\n[{i}/{len(items)}] Processing: {item}")
            if item.startswith("[out:json]"):  # It's a query
                process_query(item, args, f"batch_{i}")
            else:  # It's a place name
                process_place(item, args, f"batch_{i}")
        return
    
    # Single mode
    if args.place:
        process_place(args.place, args, args.output)
    elif args.query:
        process_query(args.query, args, args.output)
    elif args.query_file:
        process_query_file(args.query_file, args, args.output)

def process_place(place, args, output_name=None):
    """Process a place using OSMnx"""
    if output_name is None:
        output_name = args.output
    
    print(f"\n📍 Processing place: {place}")
    
    try:
        gdf = query_osmnx(place, args.feature_type)
        heatmap = create_density_from_gdf(gdf, args.grid_size, args.height_scale)
        
        # Save outputs
        output_base = Path(args.output_dir) / output_name
        
        if not args.no_png:
            export_heightmap_png(heatmap, f"{output_base}.png", args.colormap)
        
        if args.save_heatmap:
            np.save(f"{output_base}.npy", heatmap)
        
        export_obj_from_heightmap(heatmap, f"{output_base}.obj", args.height_scale)
        
        # Create MTL with texture reference
        if not args.no_png:
            export_mtl_with_texture(f"{output_base}.obj", f"{output_base}.png")
        
        print(f"\n✅ Success! Files saved to: {args.output_dir}/")
        print(f"   OBJ: {output_base}.obj")
        print(f"   PNG: {output_base}.png")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def process_query(query, args, output_name=None):
    """Process a direct Overpass query"""
    if output_name is None:
        output_name = args.output
    
    print(f"\n📝 Processing Overpass query...")
    
    try:
        coords = query_overpass(query, args.timeout)
        
        if len(coords) == 0:
            print("❌ No coordinates found in query results")
            return
        
        heatmap = create_density_heatmap(coords, args.grid_size, args.height_scale)
        
        # Save outputs
        output_base = Path(args.output_dir) / output_name
        
        if not args.no_png:
            export_heightmap_png(heatmap, f"{output_base}.png", args.colormap)
        
        if args.save_heatmap:
            np.save(f"{output_base}.npy", heatmap)
        
        export_obj_from_heightmap(heatmap, f"{output_base}.obj", args.height_scale)
        
        print(f"\n✅ Success! Files saved to: {args.output_dir}/")
        print(f"   OBJ: {output_base}.obj")
        print(f"   PNG: {output_base}.png")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def process_query_file(filepath, args, output_name=None):
    """Process a query from a file"""
    if output_name is None:
        output_name = args.output
    
    with open(filepath, 'r') as f:
        query = f.read()
    
    process_query(query, args, output_name)

if __name__ == "__main__":
    # Check for required packages
    required = ["osmnx", "geopandas", "numpy", "matplotlib", "requests"]
    missing = []
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("❌ Missing required packages. Install with:")
        print(f"   pip install {' '.join(missing)}")
        sys.exit(1)
    
    main()
