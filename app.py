import streamlit as st
import json
import pandas as pd
import io

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
            # Extract data
            table_list = []
            for table in tables:
                table_info = {
                    "Table Name": table.get("Name", ""),
                    "Description": table.get("Description", "") or table.get("Comment", ""), # Fallback to Comment
                    "Type": table.get("TableType", "") or table.get("Type", "") or "Data Table",
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
                    # Extract Prominence from ActionDefinition/ActionSettings if available
                    prominence = ""
                    if act.get("ActionDefinition"):
                        prominence = act["ActionDefinition"].get("Prominence", "")
                    
                    actions_list.append({
                        "Action Name": act.get("Name", ""),
                        "Type": act.get("ActionType", ""),
                        "Table": act.get("Table", ""),
                        "Display Name": act.get("DisplayName", "") or act.get("Name", ""), # Fallback
                        "Prominence": prominence,
                        "Condition": act.get("Condition", ""),
                        "Icon": act.get("Icon", "")
                    })
            df_actions = pd.DataFrame(actions_list)

            # --- TABS LAYOUT ---
            tab_overview, tab_details, tab_actions = st.tabs(["Tables Overview", "Table Column Details", "Actions Overview"])
            
            with tab_overview:
                st.subheader(f"All Tables ({len(tables)})")
                st.dataframe(df_tables, use_container_width=True)
            
            with tab_actions:
                st.subheader(f"All Actions ({len(actions_list)})")
                if not df_actions.empty:
                    st.dataframe(df_actions, use_container_width=True)
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
