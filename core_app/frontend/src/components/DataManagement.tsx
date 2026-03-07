import React, { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  CircularProgress,
} from "@mui/material";
import { DataGrid, GridColDef } from "@mui/x-data-grid";

export interface RawDataRow {
  id: string;
  customer_id?: string;
  brand?: string;
  fridge_model?: string;
  capacity_liters?: number;
  price?: number;
  sales_date?: string;
  store_name?: string;
  store_address?: string;
  customer_feedback?: string;
  feedback_rating?: number;
  feedback_sentiment_category?: string;
}

const COLUMNS: GridColDef[] = [
  { field: "id", headerName: "ID", width: 90, editable: false },
  { field: "customer_id", headerName: "Customer ID", width: 110, editable: true },
  { field: "brand", headerName: "Brand", width: 100, editable: true },
  { field: "fridge_model", headerName: "Model", width: 120, editable: true },
  { field: "capacity_liters", headerName: "Capacity (L)", width: 100, type: "number", editable: true },
  { field: "price", headerName: "Price", width: 100, type: "number", editable: true },
  { field: "sales_date", headerName: "Sales Date", width: 110, editable: true },
  { field: "store_name", headerName: "Store", width: 140, editable: true },
  { field: "store_address", headerName: "Address", width: 180, editable: true },
  { field: "customer_feedback", headerName: "Feedback", width: 200, editable: true },
  { field: "feedback_rating", headerName: "Rating", width: 80, type: "number", editable: true },
  { field: "feedback_sentiment_category", headerName: "Sentiment", width: 100, editable: true },
];

const DataManagement: React.FC = () => {
  const [rows, setRows] = useState<RawDataRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 25 });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRow, setEditingRow] = useState<RawDataRow | null>(null);
  const [formData, setFormData] = useState<Partial<RawDataRow>>({});
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<RawDataRow | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/rawdata?limit=${paginationModel.pageSize}&offset=${paginationModel.page * paginationModel.pageSize}`
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setRows(data.items || []);
      setTotal(data.total ?? 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [paginationModel.page, paginationModel.pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAdd = () => {
    setEditingRow(null);
    setFormData({
      id: "",
      customer_id: "",
      brand: "Unknown",
      fridge_model: "Unknown",
      capacity_liters: undefined,
      price: 0,
      sales_date: "",
      store_name: "Unknown",
      store_address: "",
      customer_feedback: "",
      feedback_rating: undefined,
      feedback_sentiment_category: "Neutral",
    });
    setDialogOpen(true);
  };

  const handleEdit = (row: RawDataRow) => {
    setEditingRow(row);
    setFormData({ ...row });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!formData.id && !editingRow) {
      setError("ID is required for new records");
      return;
    }
    const id = editingRow?.id ?? formData.id;
    if (!id) return;
    setSaving(true);
    setError(null);
    try {
      const url = editingRow ? `/rawdata/${encodeURIComponent(id)}` : "/rawdata";
      const method = editingRow ? "PUT" : "POST";
      const body = {
        id: editingRow ? undefined : formData.id,
        customer_id: formData.customer_id ?? "",
        brand: formData.brand ?? "Unknown",
        fridge_model: formData.fridge_model ?? "Unknown",
        capacity_liters: formData.capacity_liters ?? null,
        price: formData.price ?? 0,
        sales_date: formData.sales_date ?? null,
        store_name: formData.store_name ?? "Unknown",
        store_address: formData.store_address ?? "",
        customer_feedback: formData.customer_feedback ?? "",
        feedback_rating: formData.feedback_rating ?? null,
        feedback_sentiment_category: formData.feedback_sentiment_category ?? "Neutral",
      };
      if (!editingRow) (body as Record<string, unknown>).id = formData.id;
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      setDialogOpen(false);
      fetchData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (row: RawDataRow) => {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/rawdata/${encodeURIComponent(row.id)}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      setDeleteConfirm(null);
      fetchData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box sx={{ p: 2, height: "100%", display: "flex", flexDirection: "column" }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h6">Data Management</Typography>
        <Button variant="contained" onClick={handleAdd}>
          Add Record
        </Button>
      </Box>
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Box sx={{ flex: 1, minHeight: 400 }}>
        <DataGrid
          rows={rows}
          columns={[
            ...COLUMNS,
            {
              field: "actions",
              headerName: "Actions",
              width: 140,
              sortable: false,
              renderCell: (params) => (
                <>
                  <Button size="small" onClick={() => handleEdit(params.row as RawDataRow)}>
                    Edit
                  </Button>
                  <Button
                    size="small"
                    color="error"
                    onClick={() => setDeleteConfirm(params.row as RawDataRow)}
                  >
                    Delete
                  </Button>
                </>
              ),
            },
          ]}
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          paginationMode="server"
          rowCount={total}
          loading={loading}
          pageSizeOptions={[10, 25, 50, 100]}
          disableRowSelectionOnClick
          sx={{ border: "none" }}
        />
      </Box>

      <Dialog open={dialogOpen} onClose={() => !saving && setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingRow ? "Edit Record" : "Add Record"}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
            <TextField
              label="ID"
              value={formData.id ?? ""}
              onChange={(e) => setFormData((p) => ({ ...p, id: e.target.value }))}
              disabled={!!editingRow}
              required
            />
            <TextField
              label="Customer ID"
              value={formData.customer_id ?? ""}
              onChange={(e) => setFormData((p) => ({ ...p, customer_id: e.target.value }))}
            />
            <TextField
              label="Brand"
              value={formData.brand ?? ""}
              onChange={(e) => setFormData((p) => ({ ...p, brand: e.target.value }))}
            />
            <TextField
              label="Fridge Model"
              value={formData.fridge_model ?? ""}
              onChange={(e) => setFormData((p) => ({ ...p, fridge_model: e.target.value }))}
            />
            <TextField
              label="Capacity (L)"
              type="number"
              value={formData.capacity_liters ?? ""}
              onChange={(e) =>
                setFormData((p) => ({
                  ...p,
                  capacity_liters: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
            />
            <TextField
              label="Price"
              type="number"
              value={formData.price ?? ""}
              onChange={(e) =>
                setFormData((p) => ({
                  ...p,
                  price: e.target.value ? Number(e.target.value) : 0,
                }))
              }
            />
            <TextField
              label="Sales Date"
              value={formData.sales_date ?? ""}
              onChange={(e) => setFormData((p) => ({ ...p, sales_date: e.target.value }))}
              placeholder="YYYY-MM-DD"
            />
            <TextField
              label="Store Name"
              value={formData.store_name ?? ""}
              onChange={(e) => setFormData((p) => ({ ...p, store_name: e.target.value }))}
            />
            <TextField
              label="Store Address"
              value={formData.store_address ?? ""}
              onChange={(e) => setFormData((p) => ({ ...p, store_address: e.target.value }))}
              multiline
            />
            <TextField
              label="Customer Feedback"
              value={formData.customer_feedback ?? ""}
              onChange={(e) => setFormData((p) => ({ ...p, customer_feedback: e.target.value }))}
              multiline
            />
            <TextField
              label="Feedback Rating"
              type="number"
              value={formData.feedback_rating ?? ""}
              onChange={(e) =>
                setFormData((p) => ({
                  ...p,
                  feedback_rating: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
            />
            <TextField
              label="Sentiment Category"
              value={formData.feedback_sentiment_category ?? ""}
              onChange={(e) =>
                setFormData((p) => ({ ...p, feedback_sentiment_category: e.target.value }))
              }
              placeholder="Positive, Neutral, or Negative"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} variant="contained" disabled={saving}>
            {saving ? <CircularProgress size={24} /> : "Save"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!deleteConfirm} onClose={() => !saving && setDeleteConfirm(null)}>
        <DialogTitle>Delete Record</DialogTitle>
        <DialogContent>
          {deleteConfirm && (
            <Typography>
              Delete record <strong>{deleteConfirm.id}</strong>? This will also remove it from the
              query/embeddings index.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)} disabled={saving}>
            Cancel
          </Button>
          <Button
            onClick={() => deleteConfirm && handleDelete(deleteConfirm)}
            color="error"
            variant="contained"
            disabled={saving}
          >
            {saving ? <CircularProgress size={24} /> : "Delete"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DataManagement;
