import streamlit as st
import json
import pandas as pd
import io
import ast

st.set_page_config(page_title="AppSheet JSON to XLSX Converter", layout="wide")

st.title("AppSheet JSON to Excel Converter")
st.write("tolong upload json appsheet anda untuk melihat data tabel nya")

# Sidebar for Upload
with st.sidebar:
    st.header("Upload Input")
    uploaded_file = st.file_uploader("Choose a JSON file", type="json")
    st.info("Upload your AppSheet JSON definition to parse and inspect.")

if uploaded_file is not None:
    # Try different encodings
    data = None
    bytes_data = uploaded_file.getvalue()
    
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    for encoding in encodings:
        try:
            string_data = bytes_data.decode(encoding)
            data = json.loads(string_data)
            st.sidebar.success(f"Loaded: {encoding}")
            break
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError as e:
            st.sidebar.error(f"Error {encoding}: {e}")
            break
            
    if data:
        tables = []
        # Try finding tables in different locations
        if 'Template' in data and 'Tables' in data['Template']:
            tables = data['Template']['Tables']
        elif 'Template' in data and 'AppData' in data['Template'] and 'DataSets' in data['Template']['AppData']:
            tables = data['Template']['AppData']['DataSets']
        
        if tables:
            # --- PARSE SLICES FIRST ---
            slice_names = set()
            if 'Template' in data and 'AppData' in data['Template'] and 'TableSlices' in data['Template']['AppData']:
                raw_slices = data['Template']['AppData']['TableSlices']
                for sl in raw_slices:
                    slice_names.add(sl.get("Name", ""))

            # Extract data
            table_list = []
            for table in tables:
                t_name = table.get("Name", "")
                t_type = table.get("TableType", "") or table.get("Type", "") or "Data Table"
                
                # Check if it is a slice
                if t_name in slice_names:
                     t_type = "Slice"

                table_info = {
                    "Table Name": t_name,
                    "Description": table.get("Description", "") or table.get("Comment", ""), # Fallback to Comment
                    "Type": t_type,
                    "Schema Name": table.get("Schema", "") or table.get("SchemaName", ""),
                    "Source": table.get("Source", ""),
                    "SourcePath": table.get("SourcePath", ""),
                    "UpdateMode": table.get("UpdateMode", ""),
                    "AllowedUpdates": str(table.get("AllowedUpdates", "")),
                    "ReadOnly": table.get("ReadOnly", False)
                }
                table_list.append(table_info)
            
            # Create DataFrame for Tables
            df_tables = pd.DataFrame(table_list)
            
            
            # Prepare Schema Dict
            schema_dict = {}
            if 'Template' in data and 'AppData' in data['Template'] and 'DataSchemas' in data['Template']['AppData']:
                schemas = data['Template']['AppData']['DataSchemas']
                schema_dict = {schema['Name']: schema for schema in schemas}
            
            # --- PARSE ACTIONS ---
            actions_list = []
            if 'Template' in data and 'AppData' in data['Template'] and 'DataActions' in data['Template']['AppData']:
                raw_actions = data['Template']['AppData']['DataActions']
                for act in raw_actions:
                    # Extract Prominence
                    prominence = ""
                    action_def = act.get("ActionDefinition", {})
                    if action_def:
                        prominence = action_def.get("Prominence", "")
                    
                    # Derive "Do This" description
                    do_this = ""
                    atype = act.get("ActionType", "")
                    
                    if atype == "SetValues" and "ColumnValues" in action_def:
                        cols = [cv['Column'] for cv in action_def.get('ColumnValues', [])]
                        do_this = f"Set columns: {', '.join(cols)}"
                    elif atype == "AddRow" and "TableDestination" in action_def:
                        do_this = f"Add row to: {action_def['TableDestination']}"
                    elif atype == "App" and "AppMenuItemTarget" in action_def:
                        do_this = f"Go to: {action_def.get('AppMenuItemTarget','')}"
                    elif atype == "OpenUrl" and "UrlTarget" in action_def:
                        do_this = f"Open URL: {action_def.get('UrlTarget','')}"
                    elif atype == "Delete":
                        do_this = "Delete this row"
                    else:
                        # Fallback: try to find 'target' like keys
                        keys = list(action_def.keys())
                        relevant = [k for k in keys if 'Target' in k or 'Destination' in k or 'Values' in k]
                        if relevant:
                            do_this = f"Config: {', '.join(relevant)}"
                        else:
                            do_this = atype # Default to type if no specific info

                    actions_list.append({
                        "Action Name": act.get("Name", ""),
                        "Do This": do_this,
                        "Type": act.get("ActionType", ""),
                        "Formula": act.get("Condition", "") or "TRUE",
                        "Table": act.get("Table", ""),
                        "Display Name": act.get("DisplayName", "") or act.get("Name", ""),
                        "Prominence": prominence,
                        "Need Confirmation": action_def.get("NeedsConfirmation", False),
                        "Confirmation Msg": action_def.get("ConfirmationMessage", ""),
                        "Icon": act.get("Icon", ""),
                        "Modifies Data": action_def.get("ModifiesData", "")
                    })
            df_actions = pd.DataFrame(actions_list)

            # --- PARSE SLICES ---
            slices_list = []
            if 'Template' in data and 'AppData' in data['Template'] and 'TableSlices' in data['Template']['AppData']:
                raw_slices = data['Template']['AppData']['TableSlices']
                for sl in raw_slices:
                    # Extract filter formula from possible keys
                    filter_formula = sl.get("RowFilterCondition", "")
                    if not filter_formula:
                         filter_formula = sl.get("FilterCondition", "")
                    if not filter_formula:
                         filter_formula = sl.get("FilterExpression", "")

                    slices_list.append({
                        "Slice Name": sl.get("Name", ""),
                        "Source Table": sl.get("SourceTable", ""),
                        "Filter Formula": filter_formula,
                        "Update Mode": sl.get("UpdateMode", ""),
                        "Slice Columns": str(sl.get("SliceColumns", [])), # Note: JSON shows 'Columns', not 'SliceColumns'? Check structure.
                        # Wait, inspection said: 'Columns' in keys. My code uses 'SliceColumns'. 
                        # Let's fix Columns as well if I see it in Step 311. 
                        # Step 311 keys: ..., 'Columns', ... 
                        # My code used 'SliceColumns', that looks wrong too.
                        "Slice Columns": str(sl.get("Columns", [])),
                        "Actions": str(sl.get("Actions", [])) # output says 'Actions', not 'SliceActions'
                    })
            df_slices = pd.DataFrame(slices_list)

            # --- PARSE VIEWS (ROBUST) ---
            views_list = []
            
            # Helper to check if an item looks like a view
            def is_view(item):
                if not isinstance(item, dict): return False
                # User's snippet showed TableOrFolderName, ViewDefinition
                keys = item.keys()
                return ('Name' in keys and 'ViewDefinition' in keys) or \
                       ('Name' in keys and 'TableOrFolderName' in keys) or \
                       ('ViewName' in keys and 'ViewDefinition' in keys) or \
                       ('ViewType' in keys)

            raw_views = []
            
            # 1. Try Standard Locations
            if 'Template' in data and 'Presentation' in data['Template']:
                pres = data['Template']['Presentation']
                if 'Views' in pres:
                     raw_views.extend(pres['Views'])
                if 'ViewEntries' in pres: # Found in debug
                     raw_views.extend(pres['ViewEntries'])
                
                # 2. Brute force lists in Presentation
                for k, v in pres.items():
                    if k not in ['Views', 'ViewEntries'] and isinstance(v, list) and len(v) > 0:
                        if is_view(v[0]):
                             raw_views.extend(v)
            
            # 3. Try Template['Views'] (Legacy)
            if 'Template' in data and 'Views' in data['Template']:
                 raw_views.extend(data['Template']['Views'])

            for v in raw_views:
                # Extract Source Table
                source = v.get("Source", "")
                if not source: source = v.get("TableOrFolderName", "") # From user snippet
                if not source: source = v.get("ForTable", "")
                if not source: source = v.get("Table", "")
                
                # Extract Type
                v_type = v.get("ViewType", "") or v.get("Type", "")
                if not v_type:
                    # Fallback 1: 'Action' often holds the type (e.g. 'table', 'deck')
                    v_type = v.get("Action", "")
                
                if not v_type and "ViewDefinition" in v:
                     # Fallback 2: Check ViewDefinition for hints
                     vd = v["ViewDefinition"] or {}
                     if isinstance(vd, dict):
                         if "FormStyle" in vd: v_type = "Form"
                         elif "MapStyle" in vd: v_type = "Map"
                         elif "ChartType" in vd: v_type = "Chart"
                         elif "CalendarStyle" in vd: v_type = "Calendar"
                         elif "DashboardStyle" in vd: v_type = "Dashboard"
                         elif "GalleryStyle" in vd: v_type = "Gallery"
                
                # Extract Display Name
                
                # Extract Display Name
                d_name = v.get("DisplayName", "") or v.get("Name", "") or v.get("ViewName", "")

                views_list.append({
                    "View Name": v.get("Name", "") or v.get("ViewName", ""),
                    "Type": v_type,
                    "Source": source,
                    "Display Name": d_name,
                    "Show If": v.get("ShowIf", ""),
                    "Position": v.get("Position", "") or (v.get("MenuSpec", {}).get("MenuPosition", "") if isinstance(v.get("MenuSpec"), dict) else ""),
                    "Order By": str(v.get("ViewStyle", {}).get("SortDefinitions", "")) if isinstance(v.get("ViewStyle"), dict) else "",
                    "Group By": str(v.get("ViewStyle", {}).get("GroupDefinitions", "")) if isinstance(v.get("ViewStyle"), dict) else "",
                    "Definition": str(v.get("ViewDefinition", "")) # Add raw definition for debug/info
                })
            df_views = pd.DataFrame(views_list)
            # --- TABS LAYOUT ---
            tab_overview, tab_details, tab_actions, tab_slices, tab_views = st.tabs(["Tables Overview", "Table Column Details", "Actions Overview", "Slices", "Views"])
            
            with tab_overview:
                st.subheader(f"All Tables ({len(tables)})")
                st.dataframe(df_tables, use_container_width=True)
            
            with tab_actions:
                st.subheader("Actions Overview")
                
                if not df_actions.empty:
                    # Show specific columns - now including EVERYTHING
                    cols_to_show = [
                        "Action Name", "Do This", "Formula", "Type", "Table", 
                        "Need Confirmation", "Confirmation Msg", 
                        "Prominence", "Display Name", "Icon", "Modifies Data"
                    ]
                    
                    # Filter by Table
                    unique_tables = sorted(df_actions['Table'].dropna().unique().tolist())
                    unique_tables.insert(0, "All Tables")
                    
                    selected_action_table = st.selectbox("Filter Actions by Table:", unique_tables, key="action_filter")
                    
                    final_df = df_actions
                    if selected_action_table != "All Tables":
                        final_df = df_actions[df_actions['Table'] == selected_action_table]
                        st.write(f"Showing {len(final_df)} actions for table **{selected_action_table}**")
                    else:
                        st.write(f"Showing all {len(df_actions)} actions")
                    
                    # Display with specific columns
                    st.dataframe(final_df[cols_to_show], use_container_width=True)
                else:
                    st.info("No actions found.")

            with tab_details:
                st.subheader("Inspect Table Schema")
                selected_table_name = st.selectbox("Select a Table to View Columns:", df_tables['Table Name'].tolist())
                
                if selected_table_name:
                    selected_row = df_tables[df_tables['Table Name'] == selected_table_name].iloc[0]
                    schema_key = selected_row['Schema Name']
                    
                    # 1. SHOW COLUMNS
                    st.markdown("##### Columns")
                    if schema_key and schema_key in schema_dict:
                        schema_data = schema_dict[schema_key]
                        if 'Attributes' in schema_data:
                            # Parse columns for display
                            disp_cols = []
                            for col in schema_data['Attributes']:
                                # Same logic as export
                                aux_data = {}
                                if col.get('TypeAuxData'):
                                    try: aux_data = json.loads(col['TypeAuxData'])
                                    except: pass
                                
                                disp_cols.append({
                                    "Column Name": col.get("Name", ""),
                                    "Show": aux_data.get("Show_If") if aux_data.get("Show_If") else ("" if not col.get("IsHidden") else "FALSE"),
                                    "Type": col.get("Type", ""),
                                    "Valid If": aux_data.get("Valid_If", ""),
                                    "Require": aux_data.get("Required_If") if aux_data.get("Required_If") else ("TRUE" if col.get("IsRequired") else ""),
                                    "App Formula": col.get("AppFormula", ""),
                                    "Initial Value": col.get("Default") or col.get("DefaultExpression") or "",
                                    "Spreadsheet Formula": col.get("Formula", ""),
                                    "Key": col.get("IsKey", False),
                                    "Editable": aux_data.get("Editable_If") if aux_data.get("Editable_If") else ("" if col.get("DefEdit", True) else "FALSE"),
                                    "Label": col.get("IsLabel", False)
                                })
                            st.dataframe(pd.DataFrame(disp_cols), use_container_width=True)
                        else:
                            st.warning("No column attributes found in schema.")
                    else:
                        st.warning(f"Schema '{schema_key}' not found.")
                    
                    # 2. SHOW ACTIONS FOR THIS TABLE
                    st.markdown("##### Actions for this Table")
                    if not df_actions.empty:
                        # Filter actions where 'Table' matches selected_table_name
                        # Note: Table in actions might be Name or source, assuming Name matches Table Name
                        filtered_actions = df_actions[df_actions['Table'] == selected_table_name]
                        if not filtered_actions.empty:
                            st.dataframe(filtered_actions, use_container_width=True)
                        else:
                            st.info(f"No actions associated with table '{selected_table_name}'.")
                    else:
                        st.info("No actions data available.")

                    # 3. SHOW SLICES FOR THIS TABLE
                    st.markdown("##### Slices for this Table")
                    if not df_slices.empty:
                        # Filter slices where 'Source Table' matches selected_table_name
                        filtered_slices = df_slices[df_slices['Source Table'] == selected_table_name]
                        if not filtered_slices.empty:
                            st.write(f"Found {len(filtered_slices)} slices:")
                            for index, row in filtered_slices.iterrows():
                                with st.expander(f"Slice: {row['Slice Name']}"):
                                    st.markdown("**Row Filter Condition:**")
                                    st.code(row['Filter Formula'], language='sql') # Using sql highlight for formula
                                    
                                    st.write(f"**Update Mode:** {row['Update Mode']}")
                                    
                                    # Parse and display columns
                                    try:
                                        cols_str = row['Slice Columns']
                                        if cols_str:
                                            cols_list = ast.literal_eval(cols_str)
                                            if isinstance(cols_list, list) and len(cols_list) > 0:
                                                st.markdown("**Included Columns:**")
                                                # Create a clean dataframe for columns
                                                df_slice_cols = pd.DataFrame(cols_list)
                                                st.dataframe(df_slice_cols, use_container_width=True)
                                            else:
                                                st.info("No specific columns defined (All columns).")
                                    except:
                                        st.text(f"Raw Columns: {row['Slice Columns']}")
                                    
                                    st.write(f"**Slice Actions:** {row['Actions']}")
                        else:
                            st.info(f"No slices associated with table '{selected_table_name}'.")
                    else:
                        st.info("No slices data available.")

                    # 4. SHOW VIEWS FOR THIS TABLE
                    st.markdown("##### Views for this Table")
                    if not df_views.empty:
                        # Get matching slices for this table to check if view points to a slice
                        related_slices = []
                        if not df_slices.empty:
                            related_slices = df_slices[df_slices['Source Table'] == selected_table_name]['Slice Name'].tolist()
                        
                        # Filter views where 'Source' matches selected_table_name OR matches a related slice
                        matches_table = df_views['Source'] == selected_table_name
                        matches_slice = df_views['Source'].isin(related_slices)
                        
                        filtered_views = df_views[matches_table | matches_slice]
                        
                        if not filtered_views.empty:
                            st.write(f"Found {len(filtered_views)} views:")
                            for index, row in filtered_views.iterrows():
                                source_type = "Table" if row['Source'] == selected_table_name else "Slice"
                                with st.expander(f"View: {row['View Name']} ({row['Type']}) - Source: {source_type}"):
                                    st.write(f"**Source:** {row['Source']}")
                                    st.write(f"**Display Name:** {row['Display Name']}")
                                    st.write(f"**Show If:** `{row['Show If']}`")
                                    st.write(f"**Position:** {row['Position']}")
                                    if row['Order By']:
                                        st.write(f"**Sort:** '{row['Order By']}'")
                                    if row['Group By']:
                                        st.write(f"**Group:** '{row['Group By']}'")
                        else:
                            st.info(f"No views associated with table '{selected_table_name}' (or its slices).")
                    else:
                        st.info("No views data available.")




            with tab_slices:
                st.subheader("Slices Overview")
                if not df_slices.empty:
                    st.dataframe(df_slices, use_container_width=True)
                else:
                    st.info("No slices found.")

            with tab_views:
                st.subheader("Views Overview")
                if not df_views.empty:
                    st.dataframe(df_views, use_container_width=True)
                else:
                    st.info("No views found. (Checked Views, ViewEntries, and other lists in Presentation)")



            # --- Excel Conversion (Background) ---
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Main sheet
                df_tables.to_excel(writer, index=False, sheet_name='Tables Overview')
                
                # Sheet per table
                sheets_created = 0
                for table in table_list:
                    schema_name = table.get("Schema Name")
                    if schema_name and schema_name in schema_dict:
                        schema_data = schema_dict[schema_name]
                        if 'Attributes' in schema_data:
                            columns = schema_data['Attributes']
                            processed_columns = []
                            for col in columns:
                                aux_data = {}
                                if col.get('TypeAuxData'):
                                    try: aux_data = json.loads(col['TypeAuxData'])
                                    except: pass
                                
                                processed_columns.append({
                                    "Column Name": col.get("Name", ""),
                                    "Show": aux_data.get("Show_If") if aux_data.get("Show_If") else ("" if not col.get("IsHidden") else "FALSE"),
                                    "Type": col.get("Type", ""),
                                    "Valid If": aux_data.get("Valid_If", ""),
                                    "Require": aux_data.get("Required_If") if aux_data.get("Required_If") else ("TRUE" if col.get("IsRequired") else ""),
                                    "App Formula": col.get("AppFormula", ""),
                                    "Initial Value": col.get("Default") or col.get("DefaultExpression") or "",
                                    "Spreadsheet Formula": col.get("Formula", ""),
                                    "Key": col.get("IsKey", False),
                                    "Editable": aux_data.get("Editable_If") if aux_data.get("Editable_If") else ("" if col.get("DefEdit", True) else "FALSE"),
                                    "Label": col.get("IsLabel", False)
                                })
                            
                            df_schema = pd.DataFrame(processed_columns)
                            raw_sheet_name = table['Table Name']
                            sheet_name = raw_sheet_name[:30].replace("/", "_").replace("\\", "_").replace("?", "")
                            try:
                                df_schema.to_excel(writer, index=False, sheet_name=sheet_name)
                                sheets_created += 1
                            except ValueError:
                                pass # Skip duplicates

            excel_data = output.getvalue()
            
            st.sidebar.markdown("---")
            st.sidebar.download_button(
                label="📥 Download Excel File",
                data=excel_data,
                file_name="converted_tables.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        else:
            st.error("Could not find table definitions.")
    else:
        st.error("Failed to decode file.")
